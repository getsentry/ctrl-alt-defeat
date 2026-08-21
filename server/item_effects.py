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
class ConvertHealthEffect(Effect):
    """Pay health and get Block for it.

    "Convert 50 health into 100 Block". The health is spent, not lost to an
    attack, so nothing that stands in front of damage stands in front of it --
    no Block, no share on damage taken -- and nothing that answers being hit
    answers it, so Spikes send nothing back.

    It is still health falling. A threshold notices: "Health drops below 50%"
    is written about health and not about being hit.

    What comes back is Block gained like any other, so a share on Block gained
    still applies to it.

    All of it or none of it. A player with less health than the price keeps
    what they have and gains nothing, so this can never be what kills them.
    """

    health: int
    block: int

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "convert_health", "health": self.health, "block": self.block}


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
    """Gain Block, the resource that absorbs damage a point at a time.

    It says who gains it by not saying: Block only ever lands on whoever the
    clause belongs to. There was a `target_type` here that the catalogue had
    no way to set and the engine never read, and nothing in the source game
    gives Block to the other player.
    """

    block_amount: int

    #: A share of the health the owner is short of their maximum, added to
    #: the flat amount: "Gain Block equal to 40% of your missing health".
    #: Worth nothing at full health, which is when it is written to fire.
    share_of_missing_health: float = 0.0

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "block",
            "amount": self.block_amount,
            "share_of_missing_health": self.share_of_missing_health,
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
        return bool(wanted & tags) if "any" in self.counting else wanted <= tags


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

    #: How long it lasts, or -1 for the rest of the battle -- the same word a
    #: buff uses. "The Star item triggers 100% faster for 1s", "The Diamond
    #: item triggers 10% faster for 6s". A modifier on a *player* has had a
    #: clock since durations were built; one on an item had not, and the
    #: difference was nothing but where it was written.
    duration: float

    #: How much this effect may ever grant, or None for no limit.
    #:
    #: Not with a `duration`. The tally of what one item has given another is
    #: kept against the receiver, and taking a lent modifier back does not
    #: know which grant it was undoing -- so a capped, timed modifier would
    #: leave the tally saying the cap was spent when it was not. No clause
    #: wants both, and the loader refuses the pair rather than letting it go
    #: quietly wrong. Only a
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
            "duration": self.duration,
        }


@dataclass
class InflictFatigueEffect(Effect):
    """Tire somebody out: raise their fatigue level by one and deal all of it.

    The level is the one nightfall climbs, so this both hurts now and makes
    every payout after it hurt more. It works before nightfall as well as
    after -- an item that inflicts fatigue at ten seconds has the level at 3
    by the time night falls, and the first nightfall payout deals 4.
    """

    #: `enemy` or `self`, the same word every other effect uses.
    target_type: str = "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "inflict_fatigue", "target_type": self.target_type}


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
BUFFS = frozenset(
    {
        "optimized",
        "monitored",
        "calibrated",
        "regenerating",
        "spiked",
        "draining",
        "credits",
    }
)


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

    #: See Counting, and one more: `"free"` counts the squares of the zone
    #: that no item stands on -- "Destroy 4 Block for each free Star slot".
    #: The only thing counted that is not an item, and only here, because only
    #: this effect is ever asked to.
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

    #: Spending without naming what. `one` takes a single stack of a kind
    #: picked at random -- "Use a random buff to heal for 12" -- and `all`
    #: takes every stack of every buff, which is what "Use all your buffs"
    #: means. Empty spends `costs` and nothing else.
    #:
    #: A clause that spends the pool has nothing to be unable to afford, so
    #: `all` happens even with nothing to spend; `one` needs a stack.
    from_pool: str = ""

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
        return {
            "type": "stun",
            "duration": self.duration,
            "target_type": self.target_type,
        }


# What an item modifier can change. Each is a field the engine already keeps,
# so a modifier that parses has somewhere to land.
# Names the catalogue uses that nothing implements yet. Listing them is what
# lets an unknown name be a typo rather than a shrug: one of these loads as a
# gap the loader counts, anything else stops the load. Take a name off this
# list when you build it. See BACKLOG.md.
#: Names the catalogue may use for something nothing implements yet. A name
#: here loads as a gap the loader counts; anything else stops the load, which
#: is what turns a typo into an error rather than a shrug.
#:
#: Both are empty, and that is the point. Every name they held was either
#: built under a better one -- `lifesteal` is part of effect_damage,
#: `gold_gain` is `gold`, `damage_immunity` is a share of damage taken,
#: `multicast` is an extra attack -- or was never a mechanic at all:
#: `spawn_companion`, `adaptive_buff`, `free_refresh`, `shop_discount`. No
#: item declared any of them.
#:
#: Leaving them listed was not free. A name here is a name the loader accepts,
#: so `"type": "lifesteal"` would have loaded as a declared gap and done
#: nothing, where now it stops the load and says so. Add a name only when an
#: item really does declare it, and take it off when it is built.
UNBUILT_TRIGGERS: frozenset = frozenset()

UNBUILT_EFFECTS: frozenset = frozenset()

# How an item deals its damage. An item can carry other tags too -- holy,
# nature, fire -- which say what it is made of rather than how it swings.
WEAPON_KINDS = frozenset({"melee", "ranged", "magic"})

#: What a modifier on a player can change, as against one on an item. Each is
#: a share: 0.12 is twelve percent more, -0.3 is thirty percent less.
PLAYER_MODIFIERS = frozenset(
    {
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
        # Block this player gains, whichever item gave it. The other half of
        # the pair is `block_given` below, which sits on the giving item:
        # "Star items give +30% Block" scales two items in a zone and leaves
        # a third outside it alone, so it cannot be this.
        "block_gained",
        # Maximum health an item hands over: "Your opponent gains 15% less
        # maximum health from items". Not healing and not a share of damage,
        # so it is neither of the two above.
        "max_health_from_items",
        # Every attack this player makes: "for the next 1.5s, all your attacks are
        # Critical hits" is this at 1.0.
        "critical_chance",
    }
)

MODIFIER_TARGETS = frozenset({"self", "star", "diamond", "contained", "own"})

MODIFIERS = frozenset(
    {
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
        # Shares on what this item hands over rather than on what it does:
        # "Star items give +30% Block", "Star Items give +100% Vampirism".
        # A zone can scale what the items in it give without scaling what
        # anything else gives, which a modifier on the player cannot do.
        "block_given",
        "vampirism_given",
    }
)


@dataclass
class DebuffEffect(Effect):
    """Apply a debuff to enemies"""

    debuff_name: str  # One of DEBUFFS
    value: float
    #: Seconds, or -1 for the rest of the battle. "Inflict 5 Blind for 2s"
    #: is one of the few that says a number; nearly every debuff is -1.
    duration: float = -1

    #: "(unstackable)": inflicting it again does not add to what is there. It
    #: tops the stacks up to this many and refreshes the clock, so a second
    #: helping is worth nothing to somebody already carrying a full one.
    unstackable: bool = False
    accuracy: float = 1.0
    target_type: str = "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "debuff",
            "unstackable": self.unstackable,
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

    `status` names one, or is `buffs` or `debuffs` for every stack of every
    kind: "Deals +0.5 damage for each debuff of your opponent" counts the
    whole pool, and counting one named debuff would give a different and
    smaller number.

    An aura can hand this out rather than keep it: "Star items steal 3% life
    for each Luck" is a scaled modifier given to the items in a zone, and each
    of them reads its own copy against the same pool.
    """

    stat: str
    value: float
    status: str
    whose: str  # "self" or "enemy"

    #: Which items get it. `self` is the item saying it about itself, and
    #: `star`, `diamond` or `contained` hand it to the items a zone reaches.
    target_type: str = "self"

    #: How far it is allowed to grow -- "(up to 50%)". A ceiling on the
    #: reading rather than on a running total: the count can fall again, and
    #: the modifier falls back with it.
    cap: Optional[float] = None

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "modify_per_status",
            "stat": self.stat,
            "value": self.value,
            "status": self.status,
            "whose": self.whose,
        }


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
        return {
            "type": "effect_damage",
            "amount": self.amount,
            "lifesteal": self.lifesteal,
            "per_status": self.per_status,
            "whose": self.whose,
        }


@dataclass
class StaminaEffect(Effect):
    """Put CPU straight into a player's pool.

    "Regenerate 2 stamina", "Regenerate 1 stamina". Not `stat_mod`, which
    changes how big the pool is or how fast it fills; this is the pool itself
    going up now. It cannot go past the maximum, the same as regeneration.
    """

    amount: float
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "stamina",
            "amount": self.amount,
            "target_type": self.target_type,
        }


@dataclass
class ExtraAttackEffect(Effect):
    """Make an item swing again, now.

    "On stun: Triggers extra attack", "Attacks twice." The wiki, of the
    Dagger: "On stun, the Dagger attacks an extra time." It is the item's own
    attack run once more, so everything that hangs off an attack -- accuracy,
    crits, on-hit effects, Spikes -- happens again with it.

    It costs nothing. "The Dagger attacks an extra time for free on stun."

    An item with no attack has nothing to do again, which is not an error: an
    aura might hand this to whatever stands in it.
    """

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "extra_attack"}


@dataclass
class TriggerItemEffect(Counting, Effect):
    """Make other items do what they do, and leave them where they are.

    "Trigger the Star Pet", "Trigger all Star Food", "Use 11 Mana: Trigger all
    Star Food", and the one every Potion has and none of them said: **a Potion
    that is consumed also applies the effect of the Potion above it, without
    consuming that one.** The wiki calls it potion spillover and writes it on
    every Potion page in the same words.

    "The Potion above it" and "its star" are the same square. A Potion's map is
    `['*', '^', '#']`: it covers two squares and its star is the one directly
    above, marked `^` so the projection goes straight up however the item is
    turned. So this needs no idea of "above" at all.

    **What triggering runs.** Everything the item's own triggers would do, less
    two things:

    - A standing trigger is skipped. A passive is on already, and running it
      again would hand out its modifier a second time.
    - `ConsumeEffect` is skipped, which is what "without consuming it" means.
      A Potion's effects sit behind the condition that drinks it, and the
      point of spillover is getting them without paying that.

    It does not chain. The wiki says "the Potion above it" every time, in the
    singular, and a stack of four is four spillovers rather than one of depth
    four. Worth settling by playing, because the advice on the Potion Belt
    page -- "the entire setup should be vertical to make the most of the
    Potion spillover" -- reads either way.
    """

    where: str
    counting: object

    #: How many to trigger, or 0 for every one that counts.
    how_many: int

    #: `all` in the order they stand, or `random` for "trigger a random Star
    #: Food". A random pick reads the same seeded rng as everything else.
    pick: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "trigger_item",
            "where": self.where,
            "how_many": self.how_many,
            "pick": self.pick,
        }


@dataclass
class GoldEffect(Effect):
    """Gain gold, which happens between battles and never in one."""

    amount: int

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "gold", "amount": self.amount}


@dataclass
class SaleChanceEffect(Effect):
    """Change how likely the shop is to mark an item down.

    "Sale chance +3%", "Sales chance +10%". A share added to the shop's own
    chance, and it stands for as long as the item is held rather than being
    spent.
    """

    amount: float

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "sale_chance", "amount": self.amount}


#: Effects that belong to the shop rather than to a fight.
#
# Most are carried by a ShopEnteredTrigger, which the battle never walks, so
# they never reach the simulator. A SALE CHANCE IS DIFFERENT: it stands for as
# long as the item is held, so it hangs off a PassiveTrigger -- and the battle
# does walk those. It arrived at _apply_each, matched no branch, and raised.
#
# The raise is right and stays: an effect nobody handles is a bug, not
# something to ignore quietly. This names the ones that genuinely have nothing
# to do in a battle, so the check keeps its teeth for everything else. Add to
# it rather than adding another branch that does nothing.
OUTSIDE_BATTLE = (GoldEffect, SaleChanceEffect)


@dataclass
class ChoiceEffect(Effect):
    """One of these, picked at random, and not the others.

    "Randomly gain 1 Empower or gain 3 Mana and remove 2 Mana from opponent or
    ...", "Randomly gain 14 Block or 2 stamina or 2 Luck." Each choice is a
    list, because the alternatives are not always one effect each.

    Not RandomStatusEffect, which picks a *status* out of the seven. This
    picks between clauses the item wrote out.
    """

    #: The alternatives, each a list of effects that happen together.
    choices: List[List[Effect]] = field(default_factory=list)

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "choice", "choices": len(self.choices)}


@dataclass
class DestroyBlockEffect(Effect):
    """Take Block off somebody without dealing any damage.

    "Destroy 4 Block", "remove 15 Block on crit". Not damage that Block
    absorbs -- the Block is simply gone, and a target with none loses nothing.
    """

    amount: int
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "destroy_block",
            "amount": self.amount,
            "target_type": self.target_type,
        }


@dataclass
class NextAttackEffect(Effect):
    """Put something on this item's next swing, and only the next one.

    "Gain +2 damage for the next attack", "deal +9 damage on the next attack",
    "Use 1 Mana to ignore Block and deal +6 damage".

    Not `gain_damage`, which an item keeps for the rest of the battle. This is
    spent by swinging, so an item that never swings again never spends it.
    """

    #: Flat damage on that one swing.
    damage: int

    #: Whether that swing goes past Block entirely.
    ignores_block: bool

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "next_attack",
            "damage": self.damage,
            "ignores_block": self.ignores_block,
        }


@dataclass
class MaxHealthEffect(Effect):
    """Raise the ceiling, and heal by the same amount.

    Gaining maximum health in the source game gives you the health with it,
    rather than leaving a gap to fill.
    """

    amount: int

    #: A share of the maximum, added to the flat amount: "Gain 10% maximum
    #: health". Read against the maximum the battle opened on rather than the
    #: one standing now, so "10% + 15% per Star item" with two Star items
    #: comes to 40% and not 45%: shares add here, as they do everywhere else.
    share: float = 0.0

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "max_health",
            "amount": self.amount,
            "share": self.share,
        }


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
        return {"type": "reflect", "count": self.count, "target_type": self.target_type}


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

    #: What is refused. `debuff` is the wiki's own Resist; the source game
    #: also writes "chance to resist critical hits" and "chance to resist
    #: stuns", which are the same idea aimed at something else.
    against: str = "debuff"

    #: What it narrows to, and the answer depends on `against`. For a
    #: `debuff`, the debuffs it refuses, or empty for any: "50% chance to
    #: resist Blind and Cold" names two. For a `removal`, which pool it
    #: protects -- `("buff",)` or `("debuff",)` -- because a cleanse takes
    #: from one or the other and protecting your buffs says nothing about
    #: cleansing your debuffs.
    only: Tuple[str, ...] = ()

    #: A chance that grows with what its owner holds: "You have a 2% chance to
    #: resist debuffs for each Luck". {status: share per stack}.
    per_status: Dict[str, float] = field(default_factory=dict)

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "resist",
            "count": self.count,
            "chance": self.chance,
            "target_type": self.target_type,
        }


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
        return {
            "type": "player_modify",
            "stat": self.stat,
            "value": self.value,
            "target_type": self.target_type,
            "duration": self.duration,
        }


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

    #: How the kind is chosen. `random` looks again for each stack, which is
    #: how cleansing picks. `most` and `least` choose by what is already held
    #: -- "Gain 3 buffs of the type you have most of", "Gain 3 of the buff you
    #: have least of" -- and choose once, so all the stacks go to one kind.
    #:
    #: `least` counts kinds at nothing as well, since a buff you have none of
    #: is the one you have least of, and an item that says so plainly means
    #: to give you a new one.
    pick: str = "random"

    #: When `pick` is `most` or `least`, the kinds worth choosing between.
    #: Empty means all of them; "Gain 1 Luck or 1 Spikes or 1 Mana, depending
    #: on what you have the least of" names three.
    among: Tuple[str, ...] = ()

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "random_status",
            "kind": self.kind,
            "count": self.count,
            "target_type": self.target_type,
        }


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
class ShopEnteredTrigger(Trigger):
    """Fires when the shop phase begins, once per round.

    "Shop entered: Gain 3 Gold". Nothing here happens in a battle, so nothing
    here is asked for by the battle simulator: the shop is its own phase and
    reads these where it starts.
    """

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # The shop reads these; no battle event carries them

    def get_cpu_cost(self) -> float:
        return 0


@dataclass
class AuraTrigger(Counting, Trigger):
    """Fires when an item standing in this item's zone activates.

    The third direction an aura works. The other two treat a zone as somewhere
    to reach -- what it falls on, and what it counts. Here the zone is the
    cause: "Star item activates:", "6 Star item activations:".

    `after` is how many it waits for, so 1 fires on every one and 6 fires on
    every sixth. `counting` narrows what it waits on, the same way every other
    effect that reads a zone narrows it. See Counting.

    `on` is what the item in the zone has to do. An activation is the common
    one, but the source game also writes "Star Weapon hits", "Star Weapon
    crits" and "Star Potion consumed", and those are different moments: a
    weapon that misses activated and did not hit.
    """

    zone: str = "star"
    counting: object = "any"
    after: int = 1
    on: str = "activates"
    effects: List[Effect] = field(default_factory=list)

    # Runtime state: how many have happened since it last fired.
    seen: int = 0

    #: What each `on` listens to.
    WATCHES: ClassVar[dict] = {
        "activates": "item_activated",
        "hits": "on_hit",
        "crits": "on_crit",
        "consumed": "item_consumed",
    }

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        # Never asked. The engine subscribes this to WATCHES[on] directly, so
        # the event has already been decided by the time anything runs. A
        # mutation found it by rewriting this to watch the wrong thing and
        # breaking nothing at all.
        return False

    def get_cpu_cost(self) -> int:
        return 0  # The item that activated has already paid


@dataclass
class WhenAffordableTrigger(Trigger):
    """Fires as soon as its owner can pay for it, and pays.

    "Use 10 Mana: Become invulnerable for 2s (once)". The wiki says what the
    waiting looks like: "Once the player has 10 Mana, the Glowing Crown will
    spend it to grant invulnerability for 2s." It is not on a clock and it is
    not asked for -- it simply watches, and goes off the moment the price is
    met.

    Nearly every one of these ends "(once)", which is a `limit` behind it
    rather than anything this knows about. Without one it would fire again the
    next time its owner could pay, which is what an item without the word
    should do.
    """

    #: What it costs, as buff name to stacks.
    costs: Dict[str, int] = field(default_factory=dict)
    effects: List[Effect] = field(default_factory=list)

    def affordable(self, buffs: Dict[str, int]) -> bool:
        return all(buffs.get(name, 0) >= n for name, n in self.costs.items())

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # Checked on the clock, not on an event

    def get_cpu_cost(self) -> float:
        return 0  # The price is the buffs, and it is paid in full


@dataclass
class StatusChangeTrigger(Trigger):
    """Fires when somebody gains a status.

    "Regeneration gained: Gain 4 maximum health", "Empower gained: Gain 11
    maximum health", "Opponent gains buff: 15% chance to nullify it."

    `status` names one, or is empty for any of `kind`. `whose` says which
    player is watched, so an item can answer its own gains or the other
    player's.
    """

    status: str = ""
    kind: str = "buff"  # "buff" or "debuff", when `status` is empty
    whose: str = "self"
    effects: List[Effect] = field(default_factory=list)

    def watches(self, status: str, kind: str) -> bool:
        return status == self.status if self.status else kind == self.kind

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # Subscribed by event type; this is never asked

    def get_cpu_cost(self) -> float:
        return 0


@dataclass
class CounterTrigger(Trigger):
    """Fires when a running total first crosses a line.

    "45 Block reached", "10 Heat reached", "You reached 10 debuffs",
    "Opponent reaches 30 Cold", "30 Mana gained", "22 Effect-damage dealt".

    Two kinds of total, and the difference matters. `held` is what a player has
    right now, so spending it puts them back under the line; `gained` is
    everything that has ever arrived, so it only ever goes up. "30 Mana
    gained" is the second -- an item that waited for 30 Mana to be held would
    never fire beside one that spends it.

    Crossing is the trigger, not being over: like a health threshold, it fires
    on the way past and not on every tick after.
    """

    #: What is counted: a buff or debuff name, "debuffs", "buffs", "block",
    #: "effect_damage", or "health" for a share of maximum.
    counting: str = ""

    amount: float = 0.0
    whose: str = "self"
    counts: str = "held"  # "held" or "gained"

    #: Whose giving is counted, rather than the owner's whole total: "Star
    #: items gained 12 Block" counts the Block the items in the zone handed
    #: over and no other. Empty counts the player's own total, as before.
    where: str = ""

    effects: List[Effect] = field(default_factory=list)

    # Runtime state: whether it has already gone off.
    crossed: bool = False

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # Checked on the clock, where every total is visible

    def get_cpu_cost(self) -> float:
        return 0


@dataclass
class OnStunTrigger(Trigger):
    """Fires when the other player is stunned.

    "On stun: Triggers extra attack." The wiki, of the Dagger: "On stun, the
    Dagger attacks an extra time, making it stronger with stunning items like
    the Hammer."

    Three things follow from that sentence, and they are the whole rule:

    - **What it answers is the other player being stunned**, whatever did it.
      A Hammer stunning makes every Dagger in the bag swing, and so would
      anything else that stunned them.
    - **Every item with this answers the same stun.** Three Daggers and one
      stun is three extra attacks, one each.
    - **A stun on its own owner does nothing here.** Their cooldowns are the
      ones on hold, so there is no opening to take -- and an item swinging
      during its owner's own stun would be swinging while frozen.

    Nothing asks who landed it. That was tried and it is the wrong question:
    an item that stunned its own owner handed the opening to the other side,
    because "whoever is not the target" is not the same as "whoever did it".
    Asking who is stunned needs neither.
    """

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # Subscribed by event type; this is never asked

    def get_cpu_cost(self) -> float:
        return 0


@dataclass
class OutOfStaminaTrigger(Trigger):
    """Fires when its owner runs out of CPU.

    "Out of stamina: Consume this and regenerate 2 stamina and gain 1 Empower."
    The wiki: "When the player runs out of stamina the Heroic Potion is
    consumed", and of the same item: "having higher stamina demands will make
    it more likely to trigger".

    Demand is the point, so the moment is an item wanting to run and not being
    able to afford it -- not the pool reading zero. It never does read zero: an
    item that cannot pay does not pay, so what it could not afford stays in the
    pool. Watching for nothing would have waited forever.
    """

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # Subscribed by event type; this is never asked

    def get_cpu_cost(self) -> float:
        return 0


@dataclass
class OnMissTrigger(Trigger):
    """Fires when an attack misses.

    `whose` says which: "On miss: Gain 3 Luck" is this item's own swing going
    wide, and "Opponent misses attack: Gain +2 damage for the next attack" is
    the other player's.
    """

    whose: str = "self"
    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return False  # Subscribed by event type; this is never asked

    def get_cpu_cost(self) -> float:
        return 0


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
class FatigueStartTrigger(Trigger):
    """Activates once, at nightfall, when fatigue begins.

    A moment rather than a state, so it fires on the way past and not on
    every tick spent after it. There is only ever one nightfall in a battle,
    which is why it needs no `fired` flag the way a health threshold does.
    """

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "fatigue_started"

    def get_cpu_cost(self) -> float:
        return 0  # Nothing is spent noticing the sun go down


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
