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
from typing import List

from item_effects import (
    DEBUFFS,
    WEAPON_KINDS,
    AfterTrigger,
    CounterTrigger,
    AttackEffect,
    AuraTrigger,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ChanceEffect,
    CleanseEffect,
    ConditionEffect,
    ConsumeEffect,
    CostEffect,
    ExtraAttackEffect,
    FatigueStartTrigger,
    CpuDrainEffect,
    DamageDealtTrigger,
    DebuffEffect,
    Effect,
    EffectDamageEffect,
    GainDamageEffect,
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
    OnAttackTrigger,
    OnAttackedTrigger,
    OnHitTrigger,
    GoldEffect,
    OnMissTrigger,
    OnStunTrigger,
    OutOfStaminaTrigger,
    SaleChanceEffect,
    ShopEnteredTrigger,
    PassiveTrigger,
    PerCountEffect,
    PlayerModifyEffect,
    PreventDamageEffect,
    RandomStatusEffect,
    ReflectEffect,
    ResistEffect,
    StaminaEffect,
    StatModEffect,
    StatusChangeTrigger,
    StunEffect,
    TimerTrigger,
    Trigger,
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
    "calibrated": "calibrated",
    "rate_limited": "rate limited",
    "regenerating": "regenerating",
    "spiked": "spiked",
    "draining": "draining",
    "credits": "credits",
    "memory_leaked": "memory leak",
}

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
}

#: Where an effect reaches. `own` is everything the player has out; the two
#: zones are the shapes an item draws on its own map.
REACH = {
    "self": "it",
    "star": "star items",
    "diamond": "diamond items",
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
        return text[:at] + text[at].upper() + text[at + 1:]
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

    See item_effects.Counting: `"any"` is everything, and a dict narrows to
    items carrying one of the tags or all of them.
    """
    if counting == "any" or not counting:
        return noun
    wanted = set(next(iter(counting.values())))
    # The three weapon kinds together are what a player calls a weapon, and
    # "melee, ranged or magic star items" is a long way of saying so.
    if wanted == set(WEAPON_KINDS):
        return noun.replace("item", "weapon")
    tags = [tag.replace("_", " ") for tag in sorted(wanted)]
    if "all" in counting:
        return f"{noun} that are {joined(tags)}"
    # `any` means an item carrying one of them, so the tags are alternatives.
    # Joined with "and" it reads as a single item that is somehow both.
    return f"{either(tags)} {noun}"


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
                f"gain {number(buffs[0][0])} {joined([name for _, name in buffs])}")
        else:
            clauses.append(
                f"gain {joined([f'{number(n)} {name}' for n, name in buffs])}")
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
    verb = "remove" if theirs(effect.target_type) else "cleanse"
    if effect.named():
        what = f"{number(effect.count)} {marked(effect.removes)}"
    else:
        what = f"{number(effect.count)} {effect.removes}"
        if effect.count != 1:
            what += "s"
    return (verb, whom, what)


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
    return f"gain {number(effect.block_amount)} Block"


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
    text = (f"apply {what} to your opponent" if theirs(effect.target_type)
            else f"take {what} yourself")
    if effect.duration and effect.duration > 0:
        text += f" for {seconds(effect.duration)}"
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
    if effect.chance:
        return f"{who} a debuff {percent(effect.chance)} of the time"
    stacks = "debuff" if effect.count == 1 else "debuffs"
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
    if effect.count == 1:
        many = f"a random {what}"
    else:
        many = f"{number(effect.count)} random {what}s"
    return f"inflict {many}" if theirs(effect.target_type) else f"gain {many}"


def happens_once(trigger: Trigger) -> bool:
    """Whether the condition itself can only come round once in a battle"""
    return isinstance(
        trigger, (BattleStartTrigger, AfterTrigger, HealthThresholdTrigger))


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
    reach = counted(effect.counting, REACH.get(effect.target_type, effect.target_type))
    text = f"{reach} get {by_how_much(effect.stat, effect.value)}"
    if effect.cap is not None:
        text += f" (up to {percent(effect.cap)})"
    return text


@of_effect.register
def _(effect: ModifyPerEffect) -> str:
    return (
        f"{by_how_much(effect.stat, effect.value)} for each "
        f"{counted(effect.counting, f'{effect.zone} item')}"
    )


@of_effect.register
def _(effect: ModifyPerStatusEffect) -> str:
    whose = "your opponent has" if effect.whose == "enemy" else "you have"
    return (
        f"{by_how_much(effect.stat, effect.value)} for each "
        f"{marked(effect.status)} {whose}")


@of_effect.register
def _(effect: GainDamageEffect) -> str:
    reach = counted(effect.counting, REACH.get(effect.target_type, effect.target_type))
    if effect.target_type == "self":
        return f"gain {number(effect.amount)} damage"
    return f"{reach} gain {number(effect.amount)} damage"


@of_effect.register
def _(effect: PerCountEffect) -> str:
    inner = joined(gathered(effect.effects))
    return f"{inner} for each {counted(effect.counting, f'{effect.where} item')}"


@of_effect.register
def _(effect: ChanceEffect) -> str:
    inner = joined(gathered(effect.effects))
    return f"{percent(effect.chance)} chance to {inner}"


@of_effect.register
def _(effect: CostEffect) -> str:
    price = joined([f"{number(n)} {marked(name)}" for name, n in effect.costs.items()])
    inner = joined(gathered(effect.effects))
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
    return "on hit"


@of_trigger.register
def _(trigger: OnAttackTrigger) -> str:
    return "on attack"


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
    price = joined([f"{number(n)} {marked(name)}"
                    for name, n in trigger.costs.items()])
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

    # `held` is what they have now, and spending it puts them back under the
    # line; `gained` is everything that ever arrived, and only goes up.
    if trigger.counts == "gained":
        return f"once {who} {has} gained {number(trigger.amount)} {what}"
    return f"once {who} {has} {number(trigger.amount)} {what}"


@of_trigger.register
def _(trigger: AuraTrigger) -> str:
    what = counted(trigger.counting, f"{trigger.zone} item")
    if trigger.after > 1:
        return f"every {number(trigger.after)} {what} activations"
    return f"on {what} activation"


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
