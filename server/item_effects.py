"""
Improved item effects system with proper separation of concerns
Triggers determine WHEN effects happen
Effects determine WHAT happens
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Tuple

from grid_system import ItemShape

# battle_engine imports this module, so the simulator can only be named for
# type checking. Same arrangement as event_system.py.
if TYPE_CHECKING:
    from battle_engine import BattleSimulator

# ============= EFFECTS (What happens) =============


class Effect(ABC):
    """Base class for all effects"""

    @abstractmethod
    def apply(self, source, target, battle_state: "BattleSimulator"):
        """Apply this effect"""
        pass


@dataclass
class AttackEffect(Effect):
    """Deal damage to target"""

    min_damage: int
    max_damage: int
    accuracy: float

    #: What this attack starts at. Backpack Battles' Critical hits page: "All
    #: sources of damage start with a 0% crit chance, and may only gain crit
    #: chance through outside sources." Every attack in the catalogue writes
    #: 0, and writing it is the point -- 0.05 sat here as a default and was
    #: a number nobody had chosen.
    crit_chance: float
    special: Optional[str] = None  # "bypass_block", "crash", etc

    def apply(self, source, target, battle_state: "BattleSimulator"):
        # Battle system will implement damage dealing
        return {
            "type": "attack",
            "min_damage": self.min_damage,
            "max_damage": self.max_damage,
            "accuracy": self.accuracy,
            "crit_chance": self.crit_chance,
            "special": self.special,
        }


@dataclass
class HealEffect(Effect):
    """Heal the target"""

    min_heal: int
    max_heal: int
    target_type: str = "self"  # "self", "lowest_ally", "all_allies"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "heal",
            "min_heal": self.min_heal,
            "max_heal": self.max_heal,
            "target_type": self.target_type,
        }


@dataclass
class BlockEffect(Effect):
    """Gain Block, the resource that absorbs damage a point at a time."""

    block_amount: int
    target_type: str = "self"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "block",
            "amount": self.block_amount,
            "target_type": self.target_type,
        }


@dataclass
class PreventDamageEffect(Effect):
    """Stop an incoming attack dead, up to `amount`.

    Not the same thing as Block, though both reduce damage. Block is a
    stacking resource that absorbs 1 damage per stack and is spent doing it
    (see BlockEffect). This reduces damage on one attack outright and is spent on
    nothing.
    """

    amount: int

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "prevent_damage", "amount": self.amount}


@dataclass
class CpuDrainEffect(Effect):
    """Take CPU off somebody."""

    amount: float
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "cpu_drain",
            "amount": self.amount,
            "target_type": self.target_type,
        }


@dataclass
class BuffEffect(Effect):
    """Put stacks of a buff on a player."""

    buff_name: str
    value: float
    target_type: str

    #: Seconds, or -1 for the rest of the battle, which is the same word a
    #: debuff uses. "Gain 2 Empower for 8s" is one that says a number.
    duration: float = -1

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "buff",
            "buff_name": self.buff_name,
            "value": self.value,
            "target_type": self.target_type,
            "duration": self.duration,
        }


class Counting:
    """What an effect looks at, when it does not look at everything.

    `"any"` means every item: the zone or the loadout as it stands. A dict
    narrows it -- `{"any": [...]}` for an item carrying one of the tags,
    `{"all": [...]}` for one carrying all of them. A tag is a kind an item
    carries or the category it belongs to, so "nature" and "pet" both work.
    An item matches once however many tags it matches.

    Three effects narrow this way and they narrow identically, so the rule
    lives here rather than three times over.

    A plain mixin rather than a dataclass: a base dataclass puts its fields
    first, which would have reordered every constructor that inherits it.
    Each effect declares `counting` itself, in the place it reads best.
    """

    def matches(self, tags: set) -> bool:
        """Whether an item carrying `tags` is one of the ones meant."""
        if self.counting == "any":
            return True
        wanted = {t.lower() for t in next(iter(self.counting.values()))}
        return (
            bool(wanted & tags)
            if "any" in self.counting
            else wanted <= tags
        )


@dataclass
class ModifyEffect(Counting, Effect):
    """Change a number on some items.

    "Items inside trigger 10% faster", "+15% accuracy", "costs 1 less CPU".
    Nobody carries these and they do not stack, so they are not buffs. Each
    says which items it reaches, and the engine already keeps a field for it:
    `speed_mult`, `accuracy_bonus`, `damage_mult`, `cpu_discount`.

    Heat looks like a counter-example and is not. Heat is a stack a player
    carries which happens to speed their items up. This is a number on the
    items themselves, carried by no one.
    """

    stat: str
    value: float

    #: Who it reaches, the same word every other effect uses. `star` and
    #: `diamond` are the aura zones an item draws on its own map; `contained`
    #: is what a container holds; `own` is everything the player has.
    target_type: str

    #: How much this effect may ever grant, or None for no limit. Only a
    #: modifier handed out again and again -- "Star items trigger 5% faster
    #: (up to 50%)" -- can reach a limit, so an aura leaves it None. Counted
    #: per pair of items, because the limit is on what one item has given
    #: another, not on what the receiver has been given by everybody.
    cap: Optional[float]

    #: Which of those it means. See Counting. "Star Weapons deal +2 damage"
    #: is this zone narrowed to weapons; "Star items trigger 20% faster" is
    #: the same zone narrowed to nothing.
    #:
    #: The source game writes the singular -- "The Star Weapon gains 10
    #: damage" -- when an item draws a one-square star, where the only weapon
    #: that can stand there is the one. It is the zone that is small, not the
    #: rule, so a zone reaching two weapons reaches both.
    counting: object

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "modify",
            "stat": self.stat,
            "value": self.value,
            "target_type": self.target_type,
            "counting": self.counting,
            "cap": self.cap,
        }


@dataclass
class ModifyPerEffect(Counting, Effect):
    """Change a number on the item projecting the aura, once for each item
    the aura falls on.

    The other direction from ModifyEffect. "Star items trigger 20% faster"
    changes what the zone lands on; "Triggers 15% faster for each Star Food"
    changes the item projecting it, and how much depends on what is standing
    there. 37 items in the source game are written this way against 22 the
    other, so this is the commoner half.

    `counting` narrows what is worth counting: a kind an item carries, or a
    category it belongs to, or empty for anything at all. It reads the same
    tags weapons do, so "nature" and "holy" work as well as "melee".

    Nothing it counts can be changed by another aura -- a kind and a category
    are fixed before a battle -- so it does not matter what order the auras
    are worked out in.
    """

    stat: str
    value: float
    zone: str  # "star" or "diamond"

    #: What is worth counting in the zone. See Counting.
    counting: object

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "modify_per",
            "stat": self.stat,
            "value": self.value,
            "zone": self.zone,
            "counting": self.counting,
        }


DEBUFFS = frozenset({"throttled", "memory_leaked", "rate_limited"})

# Section 3.1. Ours for Heat, Empower, Luck, Regeneration, Spikes, Vampirism
# and Mana.
BUFFS = frozenset({
    "optimized",
    "monitored",
    "calibrated",
    "regenerating",
    "spiked",
    "draining",
    "credits",
})

@dataclass
class GainDamageEffect(Counting, Effect):
    """Flat damage an item picks up during a battle and keeps.

    "Gain 1 damage", "The Star Weapon gains 10 damage". It adds to what the
    weapon rolls rather than scaling it, which is why it is not a `modify`:
    a modifier multiplies, and these clauses add.

    It is kept as its own number, apart from the item's range, because the
    source game has clauses that read it back -- "remove 1 damage gained in
    battle from all opponent Weapons" takes this and leaves the weapon's own
    damage alone.
    """

    amount: int
    target_type: str
    counting: object

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "gain_damage",
            "amount": self.amount,
            "target_type": self.target_type,
        }


@dataclass
class PerCountEffect(Counting, Effect):
    """Everything behind it, once for each item that counts.

    "Gain 3 Regeneration for each Star Holy-item", "Heal 4 per Star
    Vampiric-item". ModifyPerEffect is this shape pointed at a number on an
    item; this one is pointed at what a trigger does.

    Doing the effects again is what "for each" means, so it works with every
    effect rather than needing each of them to grow an amount field. Counting
    nothing does nothing at all, which is the same answer as multiplying by
    zero and needs no special case.
    """

    where: str
    counting: object
    effects: List[Effect] = field(default_factory=list)

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "per_count", "where": self.where}


@dataclass
class CostEffect(Effect):
    """Everything behind it, if the owner can pay for it.

    "Use 3 Mana to deal +7 damage", "Use 1 Luck, 1 Heat and 1 Mana: gain 1
    Empower". All of it or none of it, like a chance: paying part of a price
    for part of a clause is not something any item does.

    What the trigger already did stands either way. "On attack: Use 3 Mana to
    deal +7 damage" swings whether or not the Mana is there -- the attack is
    the trigger and only the bonus is bought. The wiki does not spell this
    out; it is read off the way the clauses are written, where the paid part
    is always an addition to something that happened anyway.
    """

    #: What it costs, as buff name to stacks. More than one is allowed.
    costs: Dict[str, int]
    effects: List[Effect] = field(default_factory=list)

    def affordable(self, buffs: Dict[str, int]) -> bool:
        return all(buffs.get(name, 0) >= n for name, n in self.costs.items())

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "cost", "costs": dict(self.costs)}


@dataclass
class ConditionEffect(Effect):
    """Everything behind it, if the player is in the state named.

    "If your opponent has at least 10 Cold, gain 1 Empower", "If your health
    is above 70%, gain 1 Empower. Otherwise, heal for 8." The second half is
    `otherwise`, so one effect holds the whole sentence and the two halves
    cannot both happen.

    A condition is not a cost: it reads a state and spends nothing. "If you
    have at least 10 Cold" leaves the Cold where it is, where "Use 10 Cold"
    would not.
    """

    #: What is read. `status` counts one named buff or debuff; `buffs` and
    #: `debuffs` count every stack of every kind, for "If you have no
    #: debuffs"; `health` reads a share of maximum quota.
    subject: str

    #: Whose state. "self" or "enemy".
    whose: str

    #: Which status, when `subject` is `status`. Empty otherwise.
    status: str

    #: How the reading is judged: "at_least", "above", "below", "none".
    test: str

    #: What it is judged against. A share for health, a count for a status,
    #: and ignored by "none".
    amount: float

    effects: List[Effect] = field(default_factory=list)
    otherwise: List[Effect] = field(default_factory=list)

    def holds(self, reading: float) -> bool:
        if self.test == "none":
            return reading == 0
        if self.test == "at_least":
            return reading >= self.amount
        if self.test == "above":
            return reading > self.amount
        return reading < self.amount

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "condition", "subject": self.subject}


@dataclass
class StunEffect(Effect):
    """Hold every cooldown still for a while.

    Backpack Battles' Stun page: "Stun pauses all cooldowns for a certain
    amount of time." An item mid-wait keeps the wait it had left and takes it
    up again afterwards, so nothing is lost and nothing is reset.

    Two stuns at once do not add. The same page: they "exist concurrently and
    as separate debuffs based on when they were applied and when they
    individually expire" -- so what matters is the later of the two ends, and
    a stun landing inside a longer one adds nothing.

    Not a debuff, for all the page calls it one: nothing stacks and nothing
    can cleanse it, so it is not one of the three in Section 3.2.
    """

    duration: float
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "stun", "duration": self.duration,
                "target_type": self.target_type}


# What an item modifier can change. Each is a field the engine already keeps,
# so a modifier that parses has somewhere to land.
# Names the catalogue uses that nothing implements yet. Listing them is what
# lets an unknown name be a typo rather than a shrug: one of these loads as a
# gap the loader counts, anything else stops the load. Take a name off this
# list when you build it. See BACKLOG.md.
UNBUILT_TRIGGERS = frozenset({
    "on_crit",
    "on_damage",
    "on_damage_dealt",
    "on_big_damage",
    "round_start",
})

UNBUILT_EFFECTS = frozenset({
    "adaptive_buff",
    "battle_start",
    "damage_bonus",
    "damage_immunity",
    "damage_reduction",
    "deploy_phase",
    "enemy_debuff",
    "free_refresh",
    "gold_gain",
    "lifesteal",
    "multicast",
    "shop_discount",
    "spawn_companion",
    "special",
})

# How an item deals its damage. An item can carry other tags too -- holy,
# nature, fire -- which say what it is made of rather than how it swings.
WEAPON_KINDS = frozenset({"melee", "ranged", "magic"})

#: What a modifier on a player can change, as against one on an item. Each is
#: a share: 0.12 is twelve percent more, -0.3 is thirty percent less.
PLAYER_MODIFIERS = frozenset({
    # What lands on this player, so -1.0 is invulnerable. Backpack Battles'
    # Invulnerability page: "Prevents receiving any damage during a certain
    # amount of time." That is the same sentence as "take -25% damage for 7s"
    # with the number turned up, so it is the same number.
    "damage_taken",

    # Healing this player does, and healing done to them. Two clauses, one
    # each way: "Increase your healing by 4%" against "Your opponent's healing
    # is reduced by 30%".
    "healing",
    "healing_taken",

    # What this player's items cost to run: "Items use +20% stamina".
    "stamina_use",

    # Block this player gains: "Star items give +30% Block".
    "block_gained",

    # Every attack this player makes: "for the next 1.5s, all your attacks are
    # Critical hits" is this at 1.0.
    "critical_chance",
})

MODIFIER_TARGETS = frozenset({"self", "star", "diamond", "contained", "own"})

MODIFIERS = frozenset({
    "trigger_speed",
    "accuracy",
    "damage",
    "cpu_cost",

    # Flat, where `damage` multiplies. "Deals +1 damage per Spikes" adds to
    # what the weapon rolls; "+15% damage" scales it. Both are written on the
    # same items, so they cannot be the same number.
    "damage_flat",

    # The top of the range only. "Deals +1 maximum damage per Vampirism".
    "max_damage_flat",

    # Backpack Battles' Critical hits page: damage starts at 0% and only ever
    # gains crit chance from outside. This is that outside.
    "critical_chance",
})


@dataclass
class DebuffEffect(Effect):
    """Apply a debuff to enemies"""

    debuff_name: str  # One of DEBUFFS
    value: float
    #: Seconds, or -1 for the rest of the battle. "Inflict 5 Blind for 2s"
    #: is one of the few that says a number; nearly every debuff is -1.
    duration: float = -1
    accuracy: float = 1.0
    target_type: str = "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "debuff",
            "debuff_name": self.debuff_name,
            "value": self.value,
            "duration": self.duration,
            "accuracy": self.accuracy,
            "target_type": self.target_type,
        }


@dataclass
class ChanceEffect(Effect):
    """One roll, and everything behind it happens or none of it does.

    The source game writes a chance in front of a whole clause -- "12% chance
    to deal +6 damage and gain 1 Heat" -- so this holds effects rather than
    sitting on one. It is ChanceTrigger's shape, a level down: there the roll
    decides whether a trigger fires, here whether part of what it does
    happens.

    Rolling per effect instead would let the damage land and the Heat not,
    which no item in the source game can do.
    """

    chance: float
    effects: List[Effect] = field(default_factory=list)

    def happens(self, battle_state: "BattleSimulator") -> bool:
        return self.chance >= 1.0 or battle_state.rng.random() < self.chance

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "chance", "chance": self.chance}


@dataclass
class ModifyPerStatusEffect(Effect):
    """Change a number on this item, once for each stack of a status held.

    "Triggers 10% faster for each Luck", "Deals +1 damage for each Blind of
    your opponent". The counting direction of an aura asks the grid; this asks
    the player.
    """

    stat: str
    value: float
    status: str
    whose: str  # "self" or "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "modify_per_status", "stat": self.stat,
                "value": self.value, "status": self.status, "whose": self.whose}


@dataclass
class EffectDamageEffect(Effect):
    """Damage that is not an attack.

    It does not roll for accuracy, no shield answers it and Block does not
    absorb it -- there is no weapon involved. `lifesteal` heals the owner that
    share of what lands, which is how the source game writes it: "Deal 10
    Effect-damage with 100% lifesteal".

    It can still crit. The Critical hits page says so of these very items:
    "The damage effects of [certain items] are capable of inflicting critical
    hits when they activate", and "The lifesteal effects... are capable of
    inflicting critical hits, also doubling the healing to match the damage
    dealt." A crit doubles what lands, and the healing follows the damage
    because it is a share of it.

    `per_status` is what makes the amount depend on what its owner holds:
    "Deal 10 Effect-damage + 0.5 for each Spikes + 1 for each Empower". Each
    entry is a status and what one stack of it is worth.
    """

    amount: float
    lifesteal: float

    #: {status: what one stack adds}, read where the damage is worked out.
    per_status: Dict[str, float]

    #: Whose stacks are counted, per status: "self" or "enemy".
    whose: Dict[str, str]

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "effect_damage", "amount": self.amount,
                "lifesteal": self.lifesteal, "per_status": self.per_status,
                "whose": self.whose}


@dataclass
class MaxHealthEffect(Effect):
    """Raise the ceiling, and heal by the same amount.

    Gaining maximum health in the source game gives you the health with it,
    rather than leaving a gap to fill.
    """

    amount: int

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "max_health", "amount": self.amount}


@dataclass
class CleanseEffect(Effect):
    """Take N of a status off somebody.

    Two axes, and every combination works: what to take -- a buff or a debuff,
    named or any -- and who to take it from. Taking a debuff off yourself is
    called "cleanse" and taking a buff off your opponent is called "remove",
    but that is the wording differing, not the mechanic.
    """

    count: int

    #: What to take: "debuff" or "buff" for any of that kind, or the name of
    #: one. A name says which kind it is by itself, since no buff and debuff
    #: share one, so there is nothing to state twice and no way to write the
    #: contradiction that two fields allowed.
    removes: str

    target_type: str  # "self" or "enemy"

    #: Whether what is taken is kept. "Steal a random buff" is this effect
    #: pointed at the opponent with `keep` on; "Remove 1 Luck from your
    #: opponent" is the same thing with it off. The source game writes both.
    keep: bool = False

    def named(self) -> bool:
        """Whether it takes one particular status rather than any"""
        return self.removes not in ("debuff", "buff")

    def kind(self) -> str:
        """Which pool it draws from: `debuff` or `buff`"""
        if not self.named():
            return self.removes
        return "debuff" if self.removes in DEBUFFS else "buff"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "cleanse",
            "count": self.count,
            "removes": self.removes,
            "named": self.named(),
            "kind": self.kind(),
            "keep": self.keep,
            "target_type": self.target_type,
        }


@dataclass
class ReflectEffect(Effect):
    """Gain charges that turn the next debuffs back on whoever sent them.

    Backpack Battles' Reflect page: "Reflect 2 means that you will cleanse the
    next 2 stacks of debuffs applied to you, and inflict them upon the
    opponent instead." One stack per charge, however many are inflicted at
    once: "Regardless of how many stacks of a debuff is inflicted to the
    player who has Reflect, only 1 stack will be reflected per reflect."

    Not damage. It was written here as a share of damage returned, which is
    Spikes -- a different mechanic that already exists as a buff.
    """

    count: int
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "reflect", "count": self.count,
                "target_type": self.target_type}


@dataclass
class ResistEffect(Effect):
    """Gain charges, or a standing chance, that refuse a debuff outright.

    Backpack Battles' Resist page: "Resist prevents a debuff to be inflicted."
    Two forms, and an item may grant either. A chance is added to every other
    chance -- "All percent chance methods are added together to give a
    combined total chance to resist" -- and is checked before a charge is
    spent.

    Reflect goes first: "Reflect, if a check is successful, occurs before
    Resist."
    """

    #: Charges, each refusing one stack.
    count: int

    #: A standing share, held for the battle rather than spent.
    chance: float

    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "resist", "count": self.count, "chance": self.chance,
                "target_type": self.target_type}


@dataclass
class PlayerModifyEffect(Effect):
    """Change a number on a player rather than on an item.

    "Your healing is amplified by 12%", "Both players take -25% damage for
    7s", "Become invulnerable for 2s". None of these sit on an item, and none
    of them stack as a buff does, so they are neither ModifyEffect nor
    BuffEffect.

    `duration` is seconds, or -1 for the rest of the battle -- the same word
    a buff and a debuff use.
    """

    stat: str
    value: float
    target_type: str  # "self", "enemy" or "both"
    duration: float

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "player_modify", "stat": self.stat,
                "value": self.value, "target_type": self.target_type,
                "duration": self.duration}


@dataclass
class RandomStatusEffect(Effect):
    """Grant or inflict a status nobody chose.

    "Inflict a random debuff", "Gain 20 random other buffs". Picked uniformly
    over the kinds there are, one stack at a time and looking again after
    each, which is how cleansing picks and for the same reason: weighting by
    anything would need a rule the source game never gives.
    """

    #: "buff" or "debuff", which decides the pool.
    kind: str

    #: How many stacks to hand out, one pick each.
    count: int

    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "random_status", "kind": self.kind,
                "count": self.count, "target_type": self.target_type}


@dataclass
class LimitEffect(Effect):
    """Everything behind it, but only so many times in a battle.

    "(once)", "up to 3 times", "Gain 1 Vampirism (up to 5 per battle)". The
    count is kept per effect and per battle, so two items carrying the same
    clause each get their own allowance.

    Not the same as a modifier's `cap`, which limits how much one item has
    given another and can hand out part of a grant. This limits how often the
    clause happens at all, and the last one is whole or does not happen.
    """

    times: int
    effects: List[Effect] = field(default_factory=list)

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "limit", "times": self.times}


@dataclass
class StatModEffect(Effect):
    """Modify a stat (passive effect)"""

    stat_name: str  # "max_cpu", "cpu_regen", "max_health"
    value: float

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "stat_mod", "stat": self.stat_name, "value": self.value}


@dataclass
class ConsumeEffect(Effect):
    """Consume the item (remove it from battle)"""

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "consume",
            "item_id": source.uid if hasattr(source, "uid") else None,
        }


# ============= TRIGGERS (When effects happen) =============


class Trigger(ABC):
    """Base class for all triggers

    **A field the item catalogue supplies has no default.** The catalogue is
    transcribed by hand from a wiki, and a default cannot be told apart from
    a transcription that lost a value -- which is how a shield came to roll
    30% for 8 with no CPU drain, and an on-hit effect came to have no chance.
    An item that genuinely has no value for something writes it anyway: `0`
    for a shield that takes no CPU, `1.0` for an effect that always happens.

    Runtime state is different and keeps its default. `fired` and
    `current_cooldown` are the engine's own bookkeeping, not something an
    item can say.
    """

    def __init__(self, effects: List[Effect] = None):
        self.effects = effects or []

    @abstractmethod
    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        """Check if this trigger should activate"""
        pass

    @abstractmethod
    def get_cpu_cost(self) -> float:
        """Get CPU cost for this trigger"""
        pass


@dataclass
class TimerTrigger(Trigger):
    """Activates on a timer"""

    cooldown: float
    cpu_cost: float
    effects: List[Effect] = field(default_factory=list)

    # Runtime state
    current_cooldown: float = 0.0

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != "timer_tick":
            return False
        return self.current_cooldown <= 0

    def get_cpu_cost(self) -> float:
        return self.cpu_cost


@dataclass
class BattleStartTrigger(Trigger):
    """Activates once at battle start"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "battle_start"

    def get_cpu_cost(self) -> float:
        return 0  # Battle start effects are usually free


@dataclass
class HealthThresholdTrigger(Trigger):
    """Fires once, when the owner's health falls past a fraction of its
    maximum.

    **Falling past the line is the trigger, not being below it.** Nearly every
    item with one says "(once)" in its text, and the ones that do not consume
    themselves instead, which comes to the same thing. This is why `fired` is
    part of the trigger rather than left to a `ConsumeEffect` to imply: an
    item that heals below 50% and is not a potion would otherwise heal on
    every tick it spent down there.

    **It is not a damage trigger**, though it is easy to mistake for one.
    So it is checked wherever health falls rather than raised as an event
    by whatever did the falling
    """

    threshold: float  # Fraction of max health, so 0.5 is "below 50%"
    effects: List[Effect] = field(default_factory=list)

    # Runtime state, cleared between battles by rebuilding the spec
    fired: bool = False

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != "health_threshold" or self.fired:
            return False
        # The first time health is under the line is the moment it crossed,
        # since a battle starts at full health.
        return target.quota < self.threshold * target.max_quota

    def get_cpu_cost(self) -> float:
        return 0  # Nothing is spent noticing your own health


@dataclass
class DamageDealtTrigger(Trigger):
    """Activates when this item deals damage"""

    chance: float = 1.0  # Chance to trigger
    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != "damage_dealt":
            return False
        return battle_state.rng.random() < self.chance

    def get_cpu_cost(self) -> float:
        return 0  # On-hit effects are usually free


@dataclass
class ChanceTrigger(Trigger):
    """A trigger that fires its effects based on a % chance"""

    chance: float
    effects: List[Effect] = field(default_factory=list)

    # The event this trigger answers to. Subclasses name it.
    event_name: ClassVar[str] = ""

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != self.event_name:
            return False
        if self.chance >= 1.0:
            return True
        return battle_state.rng.random() < self.chance

    def get_cpu_cost(self) -> float:
        return 0  # Whatever caused the event has already paid


@dataclass
class OnHitTrigger(ChanceTrigger):
    """Activates when this item's attack hits. Doesn't fire after a miss."""
    event_name: ClassVar[str] = "on_hit"


@dataclass
class OnAttackedTrigger(ChanceTrigger):
    """Activates when the owner is attacked, and the attack hit.

    It says which kinds of attack reach it. Every shield in the source game is
    written "On attacked (Melee)", and three are "(Melee/Ranged)", so it is a
    property of the shield rather than a rule about shields.
    """

    event_name: ClassVar[str] = "on_attacked"

    #: The weapon kinds this answers to. Anything else passes it by.
    answers_to: frozenset = frozenset()


@dataclass
class AuraTrigger(Counting, Trigger):
    """Fires when an item standing in this item's zone activates.

    The third direction an aura works. The other two treat a zone as somewhere
    to reach -- what it falls on, and what it counts. Here the zone is the
    cause: "Star item activates:", "6 Star item activations:".

    `after` is how many activations it waits for, so 1 fires on every one and
    6 fires on every sixth. `counting` narrows what it waits on, the same way
    every other effect that reads a zone narrows it. See Counting.
    """

    zone: str = "star"
    counting: object = "any"
    after: int = 1
    effects: List[Effect] = field(default_factory=list)

    # Runtime state: how many have happened since it last fired.
    seen: int = 0

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "item_activated"

    def get_cpu_cost(self) -> int:
        return 0  # The item that activated has already paid


@dataclass
class AfterTrigger(Trigger):
    """Fires once, a fixed time into the battle. "After 12s: ..."

    Not a cooldown. A timer trigger reschedules itself forever; this one is
    scheduled at the start and never again.
    """

    delay: float = 0.0
    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "after"

    def get_cpu_cost(self) -> int:
        return 0


@dataclass
class OnAttackTrigger(ChanceTrigger):
    """Fires whenever this item attacks, whether it hits or misses.

    The sibling of OnHitTrigger, and the distinction matters: "'On attack'
    effects will always trigger when a weapon successfully attempts to attack
    (AKA when not out of stamina)." A miss still counts.
    """

    event_name: ClassVar[str] = "on_attack"


@dataclass
class PassiveTrigger(Trigger):
    """Always active (for stat modifications)"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "passive_apply"

    def get_cpu_cost(self) -> float:
        return 0  # Passives don't cost CPU


@dataclass
class KillTrigger(Trigger):
    """Activates when this item gets a kill"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "enemy_killed"

    def get_cpu_cost(self) -> float:
        return 0  # Kill effects are usually free


# ============= ITEM SPECIFICATION =============


@dataclass(frozen=True)
class Recipe:
    """One way to make an item.

    The ingredients are consumed. A catalyst has to be there and has to be
    touching, but it is still there afterwards -- the Mana Orb that makes a
    Spectral Dagger out of a Dagger is not used up.
    """

    ingredients: Tuple[str, ...]
    catalysts: Tuple[str, ...] = ()

    def parts(self) -> Tuple[str, ...]:
        """Every item the recipe needs on the grid, consumed or not."""
        return self.ingredients + self.catalysts


@dataclass
class ItemSpec:
    """Complete specification for an item"""

    id: str
    name: str
    category: str  # "problem", "defense", "infrastructure"
    player_class: str
    cost: int

    # Shape for multi-square items (required for all items)
    shape: ItemShape
    slug: str

    # List of triggers, each with their own effects
    triggers: List[Trigger] = field(default_factory=list)

    # Item properties
    rarity: str = "common"  # common, uncommon, rare, epic, legendary, godly

    # How the client draws this item while it has no artwork. Both are names,
    # not values: see item_looks.py for the ones that exist. A container has
    # neither, because it is drawn as the ground the items sit on.
    color: str = ""
    pattern: str = ""

    # Whether to make the item available in the shop
    in_shop: bool = True

    # What the item is, as tags: how it swings and what it is made of. Read
    # from the catalogue, where they arrive as one comma-separated string.
    kinds: frozenset = field(default_factory=frozenset)

    @property
    def is_melee(self) -> bool:
        """Whether it swings rather than shooting or casting.

        Spiked and Draining both turn on this, and so does every shield in the
        source game, which rolls only against melee.
        """
        return "melee" in self.kinds

    # The ways this item can be made, if any. Crafting any one of them makes it.
    # Ingredients are consumed; a catalyst is needed but survives. A slug here
    # that is not in the catalogue names an item we do not have, and that
    # recipe can never be completed.
    recipe: Tuple["Recipe", ...] = ()

    # Never sold, however its rarity rolls. Crafting is the only way to get one.
    recipe_only: bool = False

    # Offered only while the player holds this item. Empty means always.
    shop_needs: str = ""

