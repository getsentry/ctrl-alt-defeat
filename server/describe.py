"""What an item does, in words, built from what it actually does.

The catalogue describes behaviour as triggers holding effects, and until now
the only sentence a player ever saw was built from a flattened summary of it:
damage, or healing, or block, and a free-text note for anything else. An item
that did two things could only say one of them, and an item whose numbers were
edited kept whatever prose had been written for the old ones.

So the words are worked out from the effects themselves. Every effect says its
own piece and every trigger says the condition it happens under, which means a
line cannot disagree with the item it belongs to.

One line per trigger. An effect that holds other effects -- a chance, a cost, a
condition, a per-count -- reads as a clause with them inside it, because that
is how the source game writes them: "12% chance to deal +6 damage and gain 1
Heat" is one sentence with one roll behind it.
"""

from functools import singledispatch
from typing import Dict, List

from item_effects import (
    DEBUFFS,
    WEAPON_KINDS,
    AfterTrigger,
    AttackEffect,
    AuraTrigger,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ChanceEffect,
    ChoiceEffect,
    CleanseEffect,
    ConditionEffect,
    ConsumeEffect,
    ConvertHealthEffect,
    CostEffect,
    CounterTrigger,
    CpuDrainEffect,
    DamageDealtTrigger,
    DebuffEffect,
    DestroyBlockEffect,
    Effect,
    EffectDamageEffect,
    ExtraAttackEffect,
    FatigueStartTrigger,
    GainDamageEffect,
    GoldEffect,
    HealEffect,
    HealthThresholdTrigger,
    InflictFatigueEffect,
    ItemSpec,
    KillTrigger,
    LimitEffect,
    MaxHealthEffect,
    ModifyEffect,
    ModifyPerEffect,
    ModifyPerStatusEffect,
    NextAttackEffect,
    OnAttackedTrigger,
    OnAttackTrigger,
    OnHitTrigger,
    OnMissTrigger,
    OnStunTrigger,
    OutOfStaminaTrigger,
    PassiveTrigger,
    PerCountEffect,
    PlayerModifyEffect,
    PreventDamageEffect,
    RandomStatusEffect,
    ReflectEffect,
    ResistEffect,
    SaleChanceEffect,
    ShopEnteredTrigger,
    StaminaEffect,
    StatModEffect,
    StatusChangeTrigger,
    StunEffect,
    TimerTrigger,
    Trigger,
    TriggerItemEffect,
    WhenAffordableTrigger,
)

#: What the ten statuses are called where a player can see them. The engine
#: knows them by the names in the catalogue, which are identifiers rather than
#: words -- `memory_leaked`, `rate_limited` -- and a tooltip reading "apply 2
#: memory_leaked" is a tooltip written for whoever wrote the catalogue.
#:
#: Lower case, because what marks one out in a line is its colour rather than
#: its capitals: "apply 2 Memory Leak and gain 1 Spiked" is a sentence
#: shouting two of its words.
SHOWN = {
    "optimized": "optimised",
    "throttled": "throttled",
    "monitored": "monitored",
    # Section 3.1 names this one Compute. The identifier stays `calibrated`,
    # because the catalogue and the engine are written against it, and this is
    # the one place a player's word for it is decided.
    "calibrated": "compute",
    "rate_limited": "rate limited",
    "regenerating": "regenerating",
    "spiked": "spiked",
    "draining": "draining",
    "credits": "credits",
    "memory_leaked": "memory leak",
}

#: What the traits an item carries are called where a player can see them.
#: The catalogue keeps the source game's words -- it is imported from the
#: wiki, and an import that renamed them would have to rename them back --
#: so the words are changed here, where they are read, and nothing that
#: matches a trait against a zone has to know about it.
#:
#: A trait nobody has renamed is shown as it is written, which is how the
#: four that already fit stay as they are.
TRAIT_SHOWN = {
    "holy": "Sentinel",
    "magic": "Glitch",
    "nature": "Feral",
    "dark": "Malware",
    "vampiric": "Leeching",
    "ice": "Cryo",
    "fire": "Thermal",
    "musical": "Audio",
}


def trait(kind: str) -> str:
    """A trait as a player reads it, in the case a card shows it in"""
    return TRAIT_SHOWN.get(kind, kind.replace("_", " ").capitalize())


#: What a modifier changes, as a player would say it. The catalogue names are
#: the engine's own fields.
#: The ones that add rather than scale. A flat bonus written as a percentage
#: -- "+100% damage flat for each Spiked" -- is off by a factor of a hundred
#: and says the wrong thing besides.
FLAT = frozenset({"damage_flat", "max_damage_flat"})

STAT_SHOWN = {
    "damage_flat": "damage",
    "max_damage_flat": "maximum damage",
    "damage_taken": "damage taken",
    "healing": "healing done",
    "healing_taken": "healing received",
    "stamina_use": "CPU use",
    "block_gained": "Block gained",
    "critical_chance": "critical chance",
    "trigger_speed": "trigger speed",
    "accuracy": "accuracy",
    "damage": "damage",
    "cpu_cost": "CPU cost",
    "damage_reduction": "damage taken",
    "max_cpu": "maximum CPU",
    "cpu_regen": "CPU regeneration",
    "max_health": "maximum quota",
    "max_health_from_items": "maximum quota from items",
    "effect_damage": "direct damage",
    "spikes_limit_melee": "[buff]spiked[/buff] return against Melee blows",
    "spikes_limit_ranged": "[buff]spiked[/buff] return against Ranged blows",
    "spikes_limit_effect": "[buff]spiked[/buff] return against Effect-damage",
    "spikes_critical_chance": "[buff]spiked[/buff] critical chance",
    "block_given": "Block",
    "vampirism_given": "Vampirism",
}

#: Stats that are a share of what an item hands over, not of what it has.
#: They read with a different verb -- "Star items give +30% Block", never
#: "get" -- and their names in STAT_SHOWN are the bare noun that verb wants.
GIVEN = frozenset({"block_given", "vampirism_given"})


def having_or_giving(stat: str) -> str:
    """`get` or `give`, whichever the stat is about"""
    return "give" if stat in GIVEN else "get"


#: The two zones an item draws on its own map. Marked, so the card can show
#: them the way the board does -- the shape beside the word, in the colour the
#: squares are drawn in -- and a player reading "for each star item" can see
#: which of the two shapes on their grid that means.
ZONES = ("star", "diamond")


def zone(name: str) -> str:
    """A zone as it is read, marked as the one of the two it is"""
    return f"[{name}]{name}[/{name}]" if name in ZONES else name


#: Where an effect reaches. `own` is everything the player has out; the two
#: zones are the shapes an item draws on its own map.
REACH = {
    "self": "it",
    "star": f"{zone('star')} items",
    "diamond": f"{zone('diamond')} items",
    "contained": "the items it holds",
    "own": "all your items",
    "enemy": "your opponent",
}


def theirs(target_type: str) -> bool:
    """Whether an effect lands on your opponent.

    The engine reads exactly one word here -- `self` -- and takes everything
    else as the other player, which is how a shield answering a hit writes
    `attacker`. Read the other way round, "drain 0.3 CPU from your opponent"
    came out as "spend 0.3 CPU": the right effect, aimed at the wrong player.
    """
    return target_type != "self"


def yours(target_type: str) -> bool:
    """Whether an effect lands on you.

    A buff is the one the engine reads the other way: it goes to its owner
    unless it is named for the `enemy`. Both defaults are mirrored here rather
    than tidied into one, because a description that tidies them says the
    wrong thing about whichever word the catalogue actually used.
    """
    return target_type != "enemy"


def by_how_much(stat: str, value: float) -> str:
    """A change to a number, said the way that number changes.

    A multiplier is a percentage of what was there; a flat bonus is added to
    it, and reads as a plain number.
    """
    name = STAT_SHOWN.get(stat, stat.replace("_", " "))
    if stat in FLAT:
        return f"{signed(value)} {name}"
    return f"{signed(value * 100)}% {name}"


#: What each status does, in the words a player reads. Section 3.1 and 3.2 of
#: the design document hold the rules; these are those rules said out loud.
#:
#: `each` is what one stack is worth, and `many` is the same sentence with the
#: total in it, so a client holding six stacks can say what six come to without
#: knowing the rule that got there. A status whose worth is not a number -- the
#: credits an item spends -- carries no `each` and is only ever described one
#: way.
#:
#: Written the way an item's own lines are written -- "Every 1.6s: gain 1
#: [buff]compute[/buff]" -- because they are read on the same screen minutes
#: apart. Terse, and no sentence where a number will do. `detail` is only for a
#: rule the number does not carry, and most of them have none.
STATUS_RULES = {
    "optimized": {
        "each": 2,
        "one": "Items trigger 2% faster",
        "many": "Items trigger {total}% faster",
        "detail": "Speed-ups and slow-downs add. 1000% either way at most.",
    },
    "throttled": {
        "each": 2,
        "one": "Items trigger 2% slower",
        "many": "Items trigger {total}% slower",
        "detail": "Slow-downs and speed-ups add. 1000% either way at most.",
    },
    "monitored": {
        "each": 1,
        "one": "+1 damage to your attacks",
        "many": "+{total} damage to your attacks",
    },
    "calibrated": {
        "each": 5,
        "one": "+5% accuracy",
        "many": "+{total}% accuracy",
    },
    "rate_limited": {
        "each": 5,
        "one": "-5% accuracy",
        "many": "-{total}% accuracy",
    },
    "regenerating": {
        "each": 1,
        "one": "Heals 1 health every 2s",
        "many": "Heals {total} health every 2s",
    },
    "memory_leaked": {
        "each": 1,
        "one": "1 damage every 2s",
        "many": "{total} damage every 2s",
    },
    "spiked": {
        "each": 1,
        "one": "1 damage to melee attackers",
        "many": "{total} damage to melee attackers",
        "detail": "Only when their blow lands.",
    },
    "draining": {
        "each": 1,
        "one": "Heals 1 on a melee hit",
        "many": "Heals {total} on a melee hit",
        "detail": "Only your own melee weapons.",
    },
    "credits": {
        "one": "Spent by items that ask for it",
    },
}


def rule(status: str) -> Dict[str, object]:
    """What one stack of a status is worth, and how to say what several are.

    A status nobody has written a rule for is described by its own name and
    nothing else, so a status added to the engine without a line here shows up
    as a chip that explains nothing rather than as a crash.
    """
    written = STATUS_RULES.get(status, {})
    return {
        "status": status,
        "shown": shown(status),
        "kind": "debuff" if status in DEBUFFS else "buff",
        "each": written.get("each", 0),
        "one": written.get("one", ""),
        "many": written.get("many", ""),
        "detail": written.get("detail", ""),
    }


def every_rule() -> List[Dict[str, object]]:
    """Every status a battle can put on a fighter, in a fixed order."""
    return [rule(status) for status in sorted(SHOWN)]


def shown(status: str) -> str:
    """A status as a player reads it, and nothing more.

    Plain words: the battle log and the chips beside each fighter are drawn as
    text, and a mark left in one of them reads back as a mark.
    """
    return SHOWN.get(status, status.replace("_", " "))


def marked(status: str) -> str:
    """A status as it is read in a description, marked as the kind it is.

    The mark is a tag rather than a colour: which colour a buff is drawn in is
    the client's to decide, and the server has no business naming one. What it
    knows, and the client does not, is which of the ten are good to have.
    """
    kind = "debuff" if status in DEBUFFS else "buff"
    return f"[{kind}]{shown(status)}[/{kind}]"


def number(value: float) -> str:
    """A number without the tail of zeroes a float prints"""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def seconds(value: float) -> str:
    return f"{number(value)}s"


def percent(fraction: float) -> str:
    return f"{number(round(fraction * 100, 2))}%"


def signed(value: float) -> str:
    return f"+{number(value)}" if value >= 0 else number(value)


def span(low: float, high: float) -> str:
    """A range, or one number where both ends are the same"""
    if low == high:
        return number(low)
    return f"{number(low)}-{number(high)}"


def capital(text: str) -> str:
    """A line as it is shown, opening with a capital.

    No full stop: what an item does is a list of the things it does, and a
    stop at the end of each one is punctuation for prose that is not there.
    Not every line starts with a letter either -- a modifier opens with its
    sign, a status with the tag marking it -- and the capital goes on the
    first letter, wherever in that it falls.
    """
    at = 0
    while at < len(text) and text[at] == "[":
        # A mark round a status, which the reader never sees as text: step
        # over it, so the capital lands on the word it holds.
        shut = text.find("]", at)
        if shut < 0:
            return text
        at = shut + 1
    if at < len(text) and text[at].isalpha():
        return text[:at] + text[at].upper() + text[at + 1 :]
    return text


def joined(parts: List[str]) -> str:
    """Several clauses as one: A, B and C.

    Where a clause has an "and" of its own -- a list of buffs, a pair of
    effects inside a chance -- the last join becomes "then" instead, or the
    line ends "...and Spiked and stun your opponent", which reads as one
    thought and is two.
    """
    parts = [part for part in parts if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    last = "then" if any(" and " in part for part in parts) else "and"
    return f"{', '.join(parts[:-1])} {last} {parts[-1]}"


def either(parts: List[str]) -> str:
    """Several alternatives as one: A, B or C"""
    parts = [part for part in parts if part]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return f"{', '.join(parts[:-1])} or {parts[-1]}"


def counted(counting: object, noun: str = "items") -> str:
    """What an effect is counting, from the tags it narrows itself to.

    See item_effects.Counting: `"any"` is everything, `"free"` is the squares
    nothing stands on, and a dict narrows to items carrying one of the tags or
    all of them.
    """
    if counting == "any" or not counting:
        return noun
    if counting == "free":
        # Not items at all, so the noun it was given does not apply.
        return noun.replace("item", "free slot")
    wanted = set(next(iter(counting.values())))
    # The three weapon kinds together are what a player calls a weapon, and
    # "melee, ranged or magic star items" is a long way of saying so.
    if wanted == set(WEAPON_KINDS):
        return noun.replace("item", "weapon")
    # Lower case, because these sit in the middle of a line rather than on a
    # card: "for each Malware star item" is a sentence shouting one of its
    # words, which is the same reason a status is not capitalised either.
    tags = [trait(tag).lower() for tag in sorted(wanted)]
    if "all" in counting:
        return f"{noun} that are {joined(tags)}"
    if "none" in counting:
        # A prefix rather than "that are not", which loses its number the
        # moment the noun is singular: "a star item that are not holy".
        if len(tags) == 1:
            return f"non-{tags[0]} {noun}"
        return f"{noun} carrying none of {joined(tags)}"
    # `any` means an item carrying one of them, so the tags are alternatives.
    # Joined with "and" it reads as a single item that is somehow both.
    return f"{either(tags)} {noun}"


def counted_in(counting: object, where: str) -> str:
    """What a "for each" counts, and where it counts it.

    A zone goes in front -- "each [star]star[/star] Nature-item" -- and a
    container goes behind, because "each Nature-item inside" is how every
    clause that means a container writes it.
    """
    if where == "contained":
        return f"{counted(counting, 'item')} inside"
    if where == "own":
        return counted(counting, "item you have out")
    return counted(counting, f"{zone(where)} item")


def gathered(effects: List[Effect]) -> List[str]:
    """The clauses for a run of effects, with the repetition taken out.

    An item that grants seven buffs at once is written as seven effects and
    reads as "gain 1 Optimised, gain 1 Monitored, gain 1 Calibrated" and so on
    to the end of the line. Said once with the names after it, it is a clause
    somebody can take in.
    """
    clauses: List[str] = []
    buffs: List[tuple] = []
    taken: List[tuple] = []
    # Whatever the catalogue's order, an item is used up after it has done
    # what it does: "it is used up, cleanse 10 debuffs from yourself" is the
    # two of them the wrong way round.
    spent: List[str] = []

    def flush_buffs() -> None:
        # The same number of each is said once -- "gain 1 Optimised, Spiked
        # and Credits" -- and different numbers keep theirs.
        nonlocal buffs
        if not buffs:
            return
        if len({count for count, _ in buffs}) == 1:
            clauses.append(
                f"gain {number(buffs[0][0])} {joined([name for _, name in buffs])}"
            )
        else:
            clauses.append(
                f"gain {joined([f'{number(n)} {name}' for n, name in buffs])}"
            )
        buffs = []

    def flush_taken() -> None:
        # And for a run of statuses taken off the same person: "remove 1
        # Spiked from your opponent and remove 2 Monitored from your opponent"
        # says who twice for no reason.
        nonlocal taken
        if not taken:
            return
        verb, whom = taken[0][0], taken[0][1]
        clauses.append(f"{verb} {joined([what for _, _, what in taken])} from {whom}")
        taken = []

    for effect in effects:
        if isinstance(effect, ConsumeEffect):
            spent.append(of_effect(effect))
            continue

        if isinstance(effect, BuffEffect) and yours(effect.target_type):
            flush_taken()
            buffs.append((effect.value, marked(effect.buff_name)))
            continue

        if isinstance(effect, CleanseEffect):
            flush_buffs()
            if taken and _taking(effect)[:2] != taken[0][:2]:
                flush_taken()
            taken.append(_taking(effect))
            continue

        flush_buffs()
        flush_taken()
        said = of_effect(effect)
        if said:
            clauses.append(said)

    flush_buffs()
    flush_taken()
    return clauses + spent


def _taking(effect: CleanseEffect) -> tuple:
    """A cleanse as three parts, so a run of them can be said as one"""
    whom = "your opponent" if theirs(effect.target_type) else "yourself"
    if theirs(effect.target_type):
        # `keep` is the whole difference between taking a buff off somebody
        # and taking it for yourself, and the line said "remove" for both.
        verb = "steal" if effect.keep else "remove"
    else:
        verb = "cleanse"
    if effect.named():
        what = f"{number(effect.count)} {marked(effect.removes)}"
    else:
        what = f"{number(effect.count)} {effect.removes}"
        if effect.count != 1:
            what += "s"
    return (verb, whom, what)


def every(trigger, moment: str, once: str) -> str:
    """A trigger that waits for several of its moment, said as the count.

    "After 4 hits, gain 1 Empower" is one of these with `after` at four, and
    the line read "on hit" until it said so.
    """
    if getattr(trigger, "after", 1) > 1:
        return f"after every {number(trigger.after)} {moment}s"
    return once


# ============ What an effect does ============


@singledispatch
def of_effect(effect: Effect) -> str:
    """One clause saying what this effect does.

    Nothing for an effect nobody has written words for, which drops the clause
    rather than printing the class name at a player.
    """
    return ""


@of_effect.register
def _(effect: AttackEffect) -> str:
    text = f"deal {span(effect.min_damage, effect.max_damage)} damage"
    if effect.special == "bypass_block":
        text += ", ignoring Block"
    elif effect.special:
        text += f" ({effect.special.replace('_', ' ')})"
    if effect.accuracy >= 1.0:
        text += " and never miss"
    return text


@of_effect.register
def _(effect: HealEffect) -> str:
    return f"heal {span(effect.min_heal, effect.max_heal)}"


@of_effect.register
def _(effect: BlockEffect) -> str:
    share = (
        f"{percent(effect.share_of_missing_health)} of your missing quota"
        if effect.share_of_missing_health
        else ""
    )
    if effect.block_amount and share:
        return f"gain {number(effect.block_amount)} Block and {share} as Block"
    if share:
        return f"gain Block equal to {share}"
    return f"gain {number(effect.block_amount)} Block"


@of_effect.register
def _(effect: ConvertHealthEffect) -> str:
    return f"turn {number(effect.health)} quota into {number(effect.block)} Block"


@of_effect.register
def _(effect: PreventDamageEffect) -> str:
    return f"prevent {number(effect.amount)} damage"


@of_effect.register
def _(effect: CpuDrainEffect) -> str:
    # Taken off your opponent it is an attack on their pool; taken off you it
    # is what the item costs to do what it just did, which is how every shield
    # in the catalogue uses it.
    if theirs(effect.target_type):
        return f"drain {number(effect.amount)} CPU from your opponent"
    return f"spend {number(effect.amount)} CPU"


@of_effect.register
def _(effect: BuffEffect) -> str:
    what = f"{number(effect.value)} {marked(effect.buff_name)}"
    if not yours(effect.target_type):
        return f"give your opponent {what}"
    return f"gain {what}"


@of_effect.register
def _(effect: DebuffEffect) -> str:
    what = f"{number(effect.value)} {marked(effect.debuff_name)}"
    # Who it lands on, said either way round. A debuff nearly always goes to
    # the other player, and "apply 1 rate limited" left a reader working out
    # which of them was being rate limited.
    text = (
        f"apply {what} to your opponent"
        if theirs(effect.target_type)
        else f"take {what} yourself"
    )
    if effect.duration and effect.duration > 0:
        text += f" for {seconds(effect.duration)}"
    if effect.unstackable:
        # Worth saying: a second helping is worth nothing to somebody already
        # carrying a full one, which a player cannot guess from the number.
        text += " (does not stack)"
    if effect.accuracy < 1.0:
        text = f"{percent(effect.accuracy)} of the time, {text}"
    return text


@of_effect.register
def _(effect: StunEffect) -> str:
    whose = "your opponent" if theirs(effect.target_type) else "yourself"
    return f"stun {whose} for {seconds(effect.duration)}"


@of_effect.register
def _(effect: EffectDamageEffect) -> str:
    text = f"deal {number(effect.amount)} damage directly"
    if effect.lifesteal:
        text += f", healing {percent(effect.lifesteal)} of it"
    return text


@of_effect.register
def _(effect: MaxHealthEffect) -> str:
    share = f"{percent(effect.share)} maximum quota" if effect.share else ""
    if effect.amount and share:
        return f"gain {number(effect.amount)} maximum quota and {share}"
    if share:
        return f"gain {share}"
    return f"gain {number(effect.amount)} maximum quota"


@of_effect.register
def _(effect: ReflectEffect) -> str:
    # Charges, not damage: each one sends a stack of the next debuff back to
    # whoever applied it.
    stacks = "debuff" if effect.count == 1 else f"{number(effect.count)} debuffs"
    if theirs(effect.target_type):
        return f"make your opponent turn back the next {stacks} sent to them"
    return f"turn the next {stacks} back on whoever sends {'it' if effect.count == 1 else 'them'}"


@of_effect.register
def _(effect: ResistEffect) -> str:
    who = "your opponent refuses" if theirs(effect.target_type) else "refuse"
    what = {"critical": "a critical hit", "stun": "a stun"}.get(
        effect.against, "a debuff"
    )
    if effect.against == "removal":
        # Not refusing something sent at you but keeping something you have,
        # so it is said the way round a player reads it.
        pool = effect.only[0] if effect.only else "buff"
        whose = "your opponent's" if theirs(effect.target_type) else "your"
        if effect.count:
            return (
                f"protect {number(effect.count)} of {whose} {pool}s "
                f"from being taken"
            )
        return (
            f"protect {whose} {pool}s from being taken "
            f"{percent(effect.chance)} of the time"
        )
    elif effect.only:
        what = either([marked(name) for name in sorted(effect.only)])
    if effect.per_status:
        # A chance that grows: "2% chance to resist debuffs for each Luck".
        grows = joined(
            [
                f"{percent(rate)} for each {marked(status)}"
                for status, rate in sorted(effect.per_status.items())
            ]
        )
        return f"{who} {what} {grows} you have"
    if effect.chance:
        return f"{who} {what} {percent(effect.chance)} of the time"
    stacks = what if effect.count == 1 else f"{what}s".replace("a ", "")
    return f"{who} the next {number(effect.count)} {stacks}"


@of_effect.register
def _(effect: PlayerModifyEffect) -> str:
    stat = STAT_SHOWN.get(effect.stat, effect.stat.replace("_", " "))
    if effect.target_type == "both":
        whose = "both players'"
    else:
        whose = "your opponent's" if theirs(effect.target_type) else "your"
    # With a verb in it. "Your damage taken -25%" is a stat line rather than
    # a sentence, and these sit in the middle of one.
    way = "reduced" if effect.value < 0 else "increased"
    text = f"{whose} {stat} is {way} by {percent(abs(effect.value))}"
    if effect.duration and effect.duration > 0:
        text += f" for {seconds(effect.duration)}"
    return text


@of_effect.register
def _(effect: RandomStatusEffect) -> str:
    what = "buff" if effect.kind == "buff" else "debuff"
    if effect.pick in ("most", "least"):
        among = (
            either([marked(name) for name in sorted(effect.among)])
            if effect.among
            else f"the {what}"
        )
        many = f"{number(effect.count)} of {among} you have " f"{effect.pick} of"
    elif effect.count == 1:
        many = f"a random {what}"
    else:
        many = f"{number(effect.count)} random {what}s"
    return f"inflict {many}" if theirs(effect.target_type) else f"gain {many}"


def happens_once(trigger: Trigger) -> bool:
    """Whether the condition itself can only come round once in a battle"""
    return isinstance(
        trigger, (BattleStartTrigger, AfterTrigger, HealthThresholdTrigger)
    )


def how_often(effect: LimitEffect) -> str:
    """How many times a capped clause is allowed to happen"""
    if effect.times == 1:
        return "once"
    return f"up to {number(effect.times)} times"


@of_effect.register
def _(effect: LimitEffect) -> str:
    return f"{joined(gathered(effect.effects))} ({how_often(effect)})"


@of_effect.register
def _(effect: StatModEffect) -> str:
    stat = STAT_SHOWN.get(effect.stat_name, effect.stat_name.replace("_", " "))
    return f"{signed(effect.value)} {stat}"


@of_effect.register
def _(effect: ExtraAttackEffect) -> str:
    return "attack again"


@of_effect.register
def _(effect: DestroyBlockEffect) -> str:
    whose = "your own" if not theirs(effect.target_type) else "your opponent's"
    return f"destroy {number(effect.amount)} of {whose} Block"


@of_effect.register
def _(effect: NextAttackEffect) -> str:
    said = []
    if effect.damage:
        said.append(f"deal {number(effect.damage)} more damage")
    if effect.ignores_block:
        said.append("go past Block")
    return f"{joined(said)} on your next attack"


@of_effect.register
def _(effect: ChoiceEffect) -> str:
    return either([joined(gathered(one)) for one in effect.choices])


@of_effect.register
def _(effect: GoldEffect) -> str:
    return f"gain {number(effect.amount)} gold"


@of_effect.register
def _(effect: SaleChanceEffect) -> str:
    return f"make a sale {number(effect.amount * 100)}% more likely"


@of_effect.register
def _(effect: StaminaEffect) -> str:
    if theirs(effect.target_type):
        return f"give your opponent {number(effect.amount)} CPU"
    return f"regain {number(effect.amount)} CPU"


@of_effect.register
def _(effect: InflictFatigueEffect) -> str:
    # The level nightfall climbs, and all of it dealt at once, so it hurts now
    # and makes every payout after it hurt more.
    if theirs(effect.target_type):
        return "raise your opponent's fatigue and deal all of it"
    return "raise your own fatigue and take all of it"


@of_effect.register
def _(effect: ConsumeEffect) -> str:
    return "it is used up"


@of_effect.register
def _(effect: CleanseEffect) -> str:
    verb, whom, what = _taking(effect)
    return f"{verb} {what} from {whom}"


@of_effect.register
def _(effect: ModifyEffect) -> str:
    change = by_how_much(effect.stat, effect.value)
    if effect.target_type == "self":
        # No subject: the item is already the subject of its own line, and
        # "it get +4% trigger speed" is what naming it again came to. The
        # per-status and per-count forms have always read this way.
        text = change
    else:
        reach = counted(
            effect.counting, REACH.get(effect.target_type, effect.target_type)
        )
        text = f"{reach} {having_or_giving(effect.stat)} {change}"
    if effect.duration and effect.duration > 0:
        text += f" for {seconds(effect.duration)}"
    if effect.cap is not None:
        text += f" (up to {percent(effect.cap)})"
    return text


@of_effect.register
def _(effect: ModifyPerEffect) -> str:
    return (
        f"{by_how_much(effect.stat, effect.value)} for each "
        f"{counted_in(effect.counting, effect.zone)}"
    )


@of_effect.register
def _(effect: ModifyPerStatusEffect) -> str:
    whose = "your opponent has" if effect.whose == "enemy" else "you have"
    change = (
        f"{by_how_much(effect.stat, effect.value)} for each "
        f"{marked(effect.status)} {whose}"
    )
    if effect.cap is not None:
        change += f" (up to {percent(effect.cap)})"
    if effect.target_type == "self":
        return change
    verb = having_or_giving(effect.stat)
    return f"{REACH.get(effect.target_type, effect.target_type)} {verb} {change}"


@of_effect.register
def _(effect: GainDamageEffect) -> str:
    reach = counted(effect.counting, REACH.get(effect.target_type, effect.target_type))
    if effect.target_type == "self":
        return f"gain {number(effect.amount)} damage"
    return f"{reach} gain {number(effect.amount)} damage"


@of_effect.register
def _(effect: PerCountEffect) -> str:
    inner = joined(gathered(effect.effects))
    return f"{inner} for each {counted_in(effect.counting, effect.where)}"


@of_effect.register
def _(effect: TriggerItemEffect) -> str:
    """Making other items act, which nothing had written a line for.

    Every Potion carries one of these -- spillover, "apply the effect of the
    Potion above it" -- so every Potion has been describing that clause as
    nothing since it was built.
    """
    what = counted_in(effect.counting, effect.where)
    if effect.how_many == 1:
        one = what[:-1] if what.endswith("s") else what
        pick = "a random" if effect.pick == "random" else "the"
        return f"set off {pick} {one}, without using it up"
    if effect.how_many:
        return f"set off {number(effect.how_many)} {what}, without using them up"
    return f"set off every {what}, without using them up"


@of_effect.register
def _(effect: ChanceEffect) -> str:
    inner = joined(gathered(effect.effects))
    if effect.per_status and not effect.chance and len(effect.per_status) == 1:
        # The way the source game writes it: "7% chance for each Luck to gain
        # 3 Mana". Every clause with a growing chance is this shape.
        ((status, rate),) = effect.per_status.items()
        return f"{percent(rate)} chance for each {marked(status)} to {inner}"
    if effect.per_status:
        grows = joined(
            [
                f"{percent(rate)} for each {marked(status)}"
                for status, rate in sorted(effect.per_status.items())
            ]
        )
        return f"{percent(effect.chance)} chance, plus {grows}, to {inner}"
    return f"{percent(effect.chance)} chance to {inner}"


@of_effect.register
def _(effect: CostEffect) -> str:
    inner = joined(gathered(effect.effects))
    if effect.from_pool == "all":
        return f"use all your buffs to {inner}"
    if effect.from_pool == "one":
        return f"use a random buff to {inner}"
    price = joined([f"{number(n)} {marked(name)}" for name, n in effect.costs.items()])
    return f"use {price} to {inner}"


@of_effect.register
def _(effect: ConditionEffect) -> str:
    inner = joined(gathered(effect.effects))
    text = f"if {_reading(effect)}, {inner}"
    if effect.otherwise:
        text += f"; otherwise {joined(gathered(effect.otherwise))}"
    return text


def _reading(effect: ConditionEffect) -> str:
    """The state a condition reads, as a player would say it"""
    whose = "your opponent" if effect.whose == "enemy" else "you"
    has = "has" if effect.whose == "enemy" else "have"

    if effect.subject == "health":
        health = "their quota" if effect.whose == "enemy" else "your quota"
        if effect.test == "none":
            return f"{health} is gone"
        return f"{health} is {_comparison(effect.test)} {percent(effect.amount)}"

    if effect.subject == "status":
        what = marked(effect.status)
    else:
        what = effect.subject  # "buffs" or "debuffs"

    if effect.test == "none":
        return f"{whose} {has} no {what}"
    return f"{whose} {has} {_comparison(effect.test)} {number(effect.amount)} {what}"


def _comparison(test: str) -> str:
    return {"at_least": "at least", "above": "above", "below": "below"}.get(test, test)


# ============ When it happens ============


@singledispatch
def of_trigger(trigger: Trigger) -> str:
    """The condition a trigger's effects happen under, or nothing for a
    trigger whose effects simply stand.
    """
    return ""


@of_trigger.register
def _(trigger: TimerTrigger) -> str:
    return f"every {seconds(trigger.cooldown)}"


@of_trigger.register
def _(trigger: BattleStartTrigger) -> str:
    return "battle start"


@of_trigger.register
def _(trigger: AfterTrigger) -> str:
    return f"after {seconds(trigger.delay)}"


@of_trigger.register
def _(trigger: HealthThresholdTrigger) -> str:
    return f"first time below {percent(trigger.threshold)} quota"


@of_trigger.register
def _(trigger: OnHitTrigger) -> str:
    return every(trigger, "hit", "on hit")


@of_trigger.register
def _(trigger: OnAttackTrigger) -> str:
    return every(trigger, "attack", "on attack")


@of_trigger.register
def _(trigger: OnAttackedTrigger) -> str:
    return "when attacked"


@of_trigger.register
def _(trigger: DamageDealtTrigger) -> str:
    return "on damage"


@of_trigger.register
def _(trigger: KillTrigger) -> str:
    return "on kill"


@of_trigger.register
def _(trigger: OnMissTrigger) -> str:
    return "when your opponent misses" if theirs(trigger.whose) else "on miss"


@of_trigger.register
def _(trigger: OnStunTrigger) -> str:
    # Whatever did it. An item answers the other player being stunned, not the
    # stun its own owner is under -- there is no opening in that one.
    return "when your opponent is stunned"


@of_trigger.register
def _(trigger: OutOfStaminaTrigger) -> str:
    return "when you run out of CPU"


@of_trigger.register
def _(trigger: ShopEnteredTrigger) -> str:
    return "when the shop opens"


@of_trigger.register
def _(trigger: FatigueStartTrigger) -> str:
    return "at nightfall"


@of_trigger.register
def _(trigger: StatusChangeTrigger) -> str:
    who = "your opponent gains" if theirs(trigger.whose) else "you gain"
    if trigger.status:
        return f"when {who} {marked(trigger.status)}"
    return f"when {who} a {trigger.kind}"


@of_trigger.register
def _(trigger: WhenAffordableTrigger) -> str:
    price = joined([f"{number(n)} {marked(name)}" for name, n in trigger.costs.items()])
    return f"as soon as you can spend {price}"


@of_trigger.register
def _(trigger: CounterTrigger) -> str:
    """A running total crossing a line, said as the total it watches"""
    who = "your opponent" if theirs(trigger.whose) else "you"
    has = "has" if theirs(trigger.whose) else "have"

    if trigger.counting == "health":
        whose = "their" if theirs(trigger.whose) else "your"
        return f"once {whose} quota reaches {percent(trigger.amount)}"
    if trigger.counting == "effect_damage":
        return f"once {who} {has} dealt {number(trigger.amount)} direct damage"

    if trigger.counting in ("buffs", "debuffs"):
        what = trigger.counting
    elif trigger.counting == "block":
        what = "Block"
    else:
        what = marked(trigger.counting)

    if trigger.where:
        # Not the player's own total but what one zone has handed over:
        # "Star items gained 12 Block". `whose` and `counts` say nothing here
        # and the loader refuses to let them try.
        givers = REACH.get(trigger.where, trigger.where)
        return f"once {givers} have given {number(trigger.amount)} {what}"

    # `held` is what they have now, and spending it puts them back under the
    # line; `gained` is everything that ever arrived, and only goes up.
    if trigger.counts == "gained":
        return f"once {who} {has} gained {number(trigger.amount)} {what}"
    return f"once {who} {has} {number(trigger.amount)} {what}"


#: What each moment an aura can watch is called, as one of them and as
#: several. "Star Weapon hits" and "Star item activates" are different
#: moments, and the line said "activation" for all four of them.
MOMENTS = {
    "activates": ("activates", "activations"),
    "hits": ("hits", "hits"),
    "crits": ("lands a critical hit", "critical hits"),
    "consumed": ("is used up", "uses"),
}


@of_trigger.register
def _(trigger: AuraTrigger) -> str:
    what = counted(trigger.counting, f"{zone(trigger.zone)} item")
    one, many = MOMENTS[trigger.on]
    if trigger.after > 1:
        return f"every {number(trigger.after)} {what} {many}"
    return f"when a {what} {one}"


@of_trigger.register
def _(trigger: PassiveTrigger) -> str:
    return ""


def notes(trigger: Trigger) -> List[str]:
    """What a condition carries in brackets: what it costs, and the odds.

    Both belong to the whole trigger rather than to any one of its effects --
    one roll decides all of them, and the CPU is paid once -- so they sit in
    the heading where a player reads them before the list underneath.
    """
    said = []
    # Which weapons a shield answers, where it does not answer all of them.
    # In brackets with the odds -- "when attacked (Melee, 30%)" -- because
    # both narrow the same condition and neither is what happens.
    answers = getattr(trigger, "answers_to", None)
    if answers and set(answers) != set(WEAPON_KINDS):
        said.append("/".join(sorted(kind.title() for kind in answers)))
    cost = getattr(trigger, "cpu_cost", 0)
    if cost:
        said.append(f"{number(cost)} CPU")
    chance = getattr(trigger, "chance", None)
    if chance is not None and chance < 1.0:
        said.append(percent(chance))
    return said


# ============ The item ============


#: What marks one thing an item does, where it does more than one.
BULLET = "\u2022"

#: The order the lines come out in, whatever order the catalogue wrote them.
#: It runs with the battle: what happens as it starts, then what the item does
#: on its own beat, then what it does in answer to something, then what waits
#: on the state of the fight, and last what is simply always true.
#:
#: The catalogue's own order is nobody's decision -- it is the order somebody
#: typed the triggers in -- so two items built the same way read differently
#: and a player cannot learn where to look.
ORDER = (
    ShopEnteredTrigger,
    BattleStartTrigger,
    TimerTrigger,
    AfterTrigger,
    WhenAffordableTrigger,
    AuraTrigger,
    OnAttackTrigger,
    OnHitTrigger,
    OnMissTrigger,
    DamageDealtTrigger,
    KillTrigger,
    OnAttackedTrigger,
    OnStunTrigger,
    StatusChangeTrigger,
    OutOfStaminaTrigger,
    CounterTrigger,
    HealthThresholdTrigger,
    FatigueStartTrigger,
    PassiveTrigger,
)


def _rank(trigger: Trigger) -> int:
    """Where in a description this trigger's lines belong"""
    for at, kind in enumerate(ORDER):
        if isinstance(trigger, kind):
            return at
    # Anything nobody has placed goes last, rather than in front of the item's
    # main action because it happened to be typed first.
    return len(ORDER)


def block(trigger: Trigger) -> List[str]:
    """One trigger, as the lines a player reads.

    Everything it does on its own line, under a heading saying when. Run
    together into a sentence they were a paragraph to be parsed -- "when
    attacked by a melee weapon, 30% of the time: prevent 7 damage and spend
    0.3 CPU" -- where what a player wants is the condition once and the
    consequences under it. A trigger that does one thing stays one line: a
    heading over a list of one is a list for the sake of it.
    """
    effects = getattr(trigger, "effects", [])
    carried = notes(trigger)

    # A cap over everything the trigger does belongs with the condition, not
    # trailing the last clause: "gain 1 Calibrated and Monitored then gain 15
    # Block (once)" hangs the whole limit off the end of the Block.
    if len(effects) == 1 and isinstance(effects[0], LimitEffect):
        cap = how_often(effects[0])
        # Unless the condition is already a one-off: "the first time your
        # quota falls below 70% (once)" counts to one twice.
        if not (cap == "once" and happens_once(trigger)):
            carried.append(cap)
        effects = effects[0].effects

    does = gathered(effects)
    if not does:
        return []

    when = of_trigger(trigger)
    if when and carried:
        when = f"{when} ({', '.join(carried)})"
    if len(does) == 1:
        return [capital(f"{when}: {does[0]}" if when else does[0])]

    # A bullet says "part of what the line above asks for", so nothing carries
    # one where there is no line above: a passive holds several standing
    # clauses, and each is its own line.
    if not when:
        return [capital(one) for one in does]
    return [capital(when) + ":"] + [f"{BULLET} {capital(one)}" for one in does]


def lines(spec: ItemSpec, skipping=None) -> List[str]:
    """Everything this item does, a trigger at a time.

    Empty for an item that does nothing anybody has words for -- a container,
    or one written entirely out of effects nobody has built yet.

    The lines are in ORDER, not in the order the catalogue happens to list the
    triggers in.

    `skipping` names triggers not to say anything about. A weapon's damage,
    cooldown and CPU already have rows of their own on the card above the
    words, and "every 1.7s (0.7 CPU): deal 2-3 damage" is all three of them a
    second time. See items.stats_of, which is where those rows come from.
    """
    said: List[List[str]] = []
    # A stable sort, so two triggers of the same kind -- an item with two
    # timers -- keep the order the catalogue gave them.
    for trigger in sorted(spec.triggers or [], key=_rank):
        if skipping is not None and skipping(trigger):
            continue
        one = block(trigger)
        if one and one not in said:
            said.append(one)
    return [line for one in said for line in one]
