#!/usr/bin/env python3
"""
Test that JSON configuration system works correctly
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from battle_engine import (
    ITEM_CATALOG,
    MEMORY_LEAKED,
    BattleItem,
    BattleSimulator,
)
from config_loader import CatalogueError, ConfigLoader, config_loader
import config_loader as config_loader_module
from containers import Container
from main import generate_shop_items
from grid_system import parse_map
from item_effects import (
    ModifyPerEffect,
    BUFFS,
    DEBUFFS,
    AttackEffect,
    CleanseEffect,
    ConsumeEffect,
    CpuDrainEffect,
    DebuffEffect,
    HealEffect,
    HealthThresholdTrigger,
    OnAttackedTrigger,
    OnHitTrigger,
    PreventDamageEffect,
    ItemSpec,
    TimerTrigger,
)


def test_json_config():
    """Test that we can load and use items from JSON"""
    print("Testing JSON Configuration System")
    print("=" * 50)

    # Load configurations
    loader = ConfigLoader()
    loader.load_all()

    print(f"\n✅ Loaded {len(loader.containers)} containers from JSON")
    print(f"✅ Loaded {len(loader.items)} items from JSON")

    # Test that we can create a battle with JSON-loaded items
    sim = BattleSimulator(seed=12345)

    # Get some items from JSON config
    null_blade = loader.get_item("null_blade")
    stack_smasher = loader.get_item("stack_smasher")
    loader.get_item("firewall")  # Verify it exists
    repair_swarm = loader.get_item("healing_nanobots")

    # Room for the shapes these items actually have. A Stack Smasher is a three
    # square L inside a 2x2, so it leaves one corner of that 2x2 free.
    p1_container = Container.of("mesh_network_hub", (0, 0), "p1_hub")
    p2_container = Container.of("mesh_network_hub", (4, 0), "p2_hub")

    p1_items = [
        BattleItem(spec=null_blade, position=(0, 0), uid="p1_null"),
        BattleItem(spec=stack_smasher, position=(1, 0), uid="p1_leak"),
    ]
    p2_items = [
        BattleItem(spec=stack_smasher, position=(4, 0), uid="p2_null2"),
        # (5, 1) is under the Stack Smasher, so this sits clear of it.
        BattleItem(spec=repair_swarm, position=(6, 0), uid="p2_health"),
    ]

    # Run battle
    print("\n🎮 Running test battle with JSON-loaded items...")
    result = sim.simulate_battle(
        p1_items,
        p2_items,
        round_number=1,
        p1_containers=[p1_container],
        p2_containers=[p2_container],
    )

    print(f"✅ Battle completed! Winner: Player {result['winner']}")
    print(f"   Duration: {result['duration']:.1f}s")
    print(f"   Total actions: {len(result['actions'])}")

    # Test some specific items
    print("\n📋 Testing specific items from JSON:")

    # Test a problem item
    ddos = loader.get_item("denier_of_service")
    if ddos:
        print(f"✅ DDoS Attack: {ddos.name} ({ddos.rarity})")
        print(f"   Shape: {ddos.shape.name if ddos.shape else 'None'}")
        print(f"   Triggers: {len(ddos.triggers)}")

    # Test a defense item
    quantum_fw = loader.get_item("quantum_firewall")
    if quantum_fw:
        print(f"✅ Quantum Firewall: {quantum_fw.name} ({quantum_fw.rarity})")
        print(f"   Category: {quantum_fw.category}")
        print(f"   Triggers: {len(quantum_fw.triggers)}")

    # Test a container
    orchestrator = loader.get_container("container_orchestrator")
    if orchestrator:
        print(f"\n✅ Container Orchestrator: {orchestrator.name}")
        print(f"   Shape: {orchestrator.shape.name if orchestrator.shape else 'None'}")
        print(f"   Cost: {orchestrator.cost}")

    print("\n" + "=" * 50)
    print("✨ JSON Configuration System Test Complete!")
    print("\nThe system successfully:")
    print("  • Loaded items and containers from JSON files")
    print("  • Created battle-ready items from configurations")
    print("  • Ran a complete battle simulation")
    print("\nYou can now easily add/modify items by editing:")
    print("  • data/items/*.json (category-specific item files)")
    print("  • data/containers.json")


if __name__ == "__main__":
    test_json_config()


class TestShopVisibility:
    """An item can exist without the shop offering it"""
    def test_items_are_offered_unless_told_otherwise(self):

        spec = config_loader.items["null_blade"]
        assert spec.in_shop is True

    def test_the_shop_skips_an_item_that_is_not_offered(self):
        # Items arrive from Backpack Battles with numbers and no behaviour.
        # They have to be able to sit in the catalogue without a player
        # being able to buy one.

        hidden = "null_blade"
        original = ITEM_CATALOG[hidden]
        with patch.dict(ITEM_CATALOG, {hidden: original.__class__(
            **{**original.__dict__, "in_shop": False}
        )}):
            offered = set()
            for seed in range(120):
                offered |= {i.item_type for i in generate_shop_items(1, seed) if i}
        assert hidden not in offered, "a hidden item should never reach the shop"
        assert len(offered) > 5, "the rest of the catalogue should still be offered"


class TestItemsSetAside:
    """`data/unavailable_items.json` holds items this game will never have.

    Each exists to put another class's items in the shop, and those classes are
    not being made, so there is nothing to build. They are kept rather than
    deleted so a later scrape does not add them back, which means the one thing
    worth testing is that keeping them cannot leak them into the game.
    """

    @staticmethod
    def _set_aside() -> dict:

        path = Path(__file__).parent.parent / "data" / "unavailable_items.json"
        return json.loads(path.read_text())

    def test_it_sits_outside_the_directory_the_loader_reads(self):
        """ConfigLoader globs data/items/*.json. A file in there is loaded, so
        this one has to be a sibling of that directory rather than inside it."""

        data = Path(__file__).parent.parent / "data"
        assert (data / "unavailable_items.json").exists()
        assert not list((data / "items").glob("unavailable*.json"))

    def test_there_are_some(self):
        # Six class badges. If this finds none, the tests below pass without
        # checking anything.
        assert len(self._set_aside()["items"]) >= 6

    def test_each_one_says_why(self):
        for item_id, config in self._set_aside()["items"].items():
            why = config.get("why", "")
            assert len(why) > 20, f"{item_id} is set aside but does not say why"

    def test_none_of_them_is_in_the_catalogue(self):

        loaded = set(config_loader.items) | set(config_loader.containers)
        clashes = sorted(set(self._set_aside()["items"]) & loaded)
        assert not clashes, f"{clashes} are set aside and loaded anyway"

    def test_the_shop_never_offers_one(self):

        set_aside = set(self._set_aside()["items"])
        offered = {
            offer.item_type
            for seed in range(200)
            for offer in generate_shop_items(1, seed)
            if offer
        }
        assert not (offered & set_aside), f"the shop offered {offered & set_aside}"

class TestOnHitLoading:
    """An on_hit trigger and a debuff effect have to survive the load"""
    def test_virus_injector_matches_belladonnas_shade(self):
        """Its numbers come from the source item, so they are worth pinning"""
        spec = config_loader.items["virus_injector"]
        timer, on_hit = spec.triggers

        assert isinstance(timer, TimerTrigger)
        assert timer.cooldown == 1.7
        assert timer.cpu_cost == 0.7
        attack = timer.effects[0]
        assert isinstance(attack, AttackEffect)
        assert (attack.min_damage, attack.max_damage) == (4, 11)
        assert attack.accuracy == 0.85

        # "On hit: 70% chance to inflict 2 Poison. The same 70% roll also
        # inflicts a random debuff." One roll, two things behind it.
        assert isinstance(on_hit, OnHitTrigger)
        assert on_hit.chance == 0.7
        assert len(on_hit.effects) == 2

    def test_the_debuff_effect_is_not_dropped(self):
        """The loader had no debuff branch, so every debuff in the
        catalogue was silently thrown away at startup"""

        debuff = config_loader.items["virus_injector"].triggers[1].effects[0]
        assert isinstance(debuff, DebuffEffect)
        assert debuff.debuff_name == "memory_leaked"
        assert debuff.value == 2

    def test_the_debuff_never_wears_off(self):
        """Section 3.2: a debuff lasts to the end of the battle"""

        debuff = config_loader.items["virus_injector"].triggers[1].effects[0]
        assert debuff.duration == -1

    def test_the_engine_reads_the_name_the_catalogue_writes(self):
        """The engine pays poison out by name. A disagreement between the two
        spellings would tick nothing, and nothing would say so."""

        debuff = config_loader.items["virus_injector"].triggers[1].effects[0]
        assert debuff.debuff_name == MEMORY_LEAKED


class TestCatalogueStrictness:
    """A wrong item should fail loudly, not quietly do nothing"""
    def loader(self):

        return ConfigLoader()

    def test_an_on_hit_trigger_has_to_state_its_chance(self):
        """Both forms exist in the source game -- the Axe is a flat "On hit:
        gain 1 damage", the Torch a "25% chance" -- so a missing chance cannot
        be told apart from an import that lost one."""

        with pytest.raises(ValueError, match="chance"):
            self.loader()._parse_trigger(
                {"type": "on_hit", "effects": []}, "some_item"
            )

    def test_an_always_on_effect_writes_one(self):

        trigger = self.loader()._parse_trigger(
            {"type": "on_hit", "chance": 1.0, "effects": []}, "some_item"
        )
        assert isinstance(trigger, OnHitTrigger)
        assert trigger.chance == 1.0

    def test_a_debuff_nothing_ticks_is_refused(self):
        """`virus` and `corruption` were both in the catalogue. Neither is a
        debuff, so both were carried on the player and read by nothing, which
        looks exactly like a working debuff until you check the damage."""

        for invented in ["virus", "corruption", "slow", "speed"]:
            with pytest.raises(ValueError, match="not a debuff"):
                self.loader()._parse_effect(
                    {"type": "debuff", "debuff_name": invented, "value": 1},
                    "some_item",
                )

    def test_the_error_names_the_item(self):
        """A catalogue of 95 items is no use to debug without the name"""
        with pytest.raises(ValueError, match="prize_item"):
            self.loader()._parse_effect(
                {"type": "debuff", "debuff_name": "virus"}, "prize_item"
            )

    def test_stat_is_no_longer_a_way_to_name_a_debuff(self):
        """One key. Two spellings is how "speed" became a debuff."""
        with pytest.raises(ValueError, match="not a debuff"):
            self.loader()._parse_effect(
                {"type": "debuff", "stat": "speed", "value": -0.2}, "some_item"
            )

    def test_every_debuff_in_the_catalogue_is_one_the_engine_ticks(self):
        """The catalogue is imported by hand from a wiki, so this is the
        check that the whole of it survived the import."""

        found = [
            effect
            for spec in config_loader.items.values()
            for trigger in spec.triggers or []
            for effect in getattr(trigger, "effects", []) or []
            if isinstance(effect, DebuffEffect)
        ]
        assert found, "the catalogue should still have debuffs in it"
        assert {e.debuff_name for e in found} <= DEBUFFS


class TestShieldsMatchTheirSources:
    """Every shield number comes from the item it is based on"""

    # Quoted from the wiki, one roll and its consequences per shield:
    #   Wooden Buckler  "On attacked (Melee): 30% chance to prevent 7 damage
    #                    and remove 0.3 stamina from opponent."
    #   Hero Shield     "... prevent 15 damage, remove 0.4 stamina."
    #   Frozen Buckler  "... prevent 12 damage, remove 0.9 stamina, and
    #                    inflict 1 Cold (up to 10)."
    #   Spiked Shield   "... prevent 9 damage, remove 0.3 stamina, and gain
    #                    1 Spikes (up to 5)."
    SOURCES = {
        "error_monitoring": ("Wooden Buckler", 0.3, 7, 0.3),
        "firewall": ("Wooden Buckler", 0.3, 7, 0.3),
        "rate_limiter": ("Hero Shield", 0.3, 15, 0.4),
        "encryption_layer": ("Frozen Buckler", 0.3, 12, 0.9),
        "quantum_firewall": ("Spiked Shield", 0.3, 9, 0.3),
    }

    def shield(self, item_id):

        (trigger,) = [
            t
            for t in config_loader.items[item_id].triggers
            if isinstance(t, OnAttackedTrigger)
        ]
        return trigger

    def test_each_shield_has_its_own_numbers(self):

        for item_id, (_, chance, prevent, drain) in self.SOURCES.items():
            trigger = self.shield(item_id)
            assert trigger.chance == chance, item_id
            stop, steal = trigger.effects[0], trigger.effects[1]
            assert isinstance(stop, PreventDamageEffect) and stop.amount == prevent
            assert isinstance(steal, CpuDrainEffect) and steal.amount == drain

    def test_every_shield_rolls_thirty_percent(self):
        """Not one shield in the source game rolls anything else, so a
        different figure is an import that went wrong, not a design choice."""
        for item_id in self.SOURCES:
            assert self.shield(item_id).chance == 0.3, item_id

    def test_the_roll_covers_the_whole_list(self):
        """A shield can never prevent the damage and miss the stamina. The
        source game writes one chance in front of both."""
        for item_id in self.SOURCES:
            trigger = self.shield(item_id)
            assert len(trigger.effects) >= 2
            # The chance lives on the trigger, so no effect carries its own.
            assert not any(hasattr(e, "chance") for e in trigger.effects), item_id

    def test_an_on_attacked_trigger_has_to_state_its_chance(self):

        with pytest.raises(ValueError, match="chance"):
            ConfigLoader()._parse_trigger(
                {"type": "on_attacked", "effects": []}, "some_shield"
            )

    def test_both_effects_have_to_state_a_value(self):
        """No defaults. A number that never arrived would otherwise load as a
        working shield."""

        for effect_type in ["prevent_damage", "cpu_drain"]:
            with pytest.raises(ValueError, match="value"):
                ConfigLoader()._parse_effect({"type": effect_type}, "some_shield")


class TestPreventDamageStaysWhereItWorks:
    """It is the one effect that cannot apply itself.

    Every other effect acts on a player. Preventing damage has to hand a
    number back so the attack can be reduced by it, and only the on_attacked
    handler asks for that. In any other trigger it would load cleanly and do
    nothing at all.
    """

    def test_the_loader_refuses_it_in_another_trigger(self):

        block = {"type": "prevent_damage", "value": 7}
        for trigger in ["timer", "battle_start", "passive", "damage_taken"]:
            with pytest.raises(ValueError, match="on_attacked"):
                ConfigLoader()._parse_trigger(
                    {"type": trigger, "chance": 1.0, "cooldown": 1.0,
                     "effects": [block]},
                    "some_item",
                )

    def test_it_is_allowed_in_on_attacked(self):

        trigger = ConfigLoader()._parse_trigger(
            {"type": "on_attacked", "chance": 0.3, "answers_to": ["melee"],
             "effects": [{"type": "prevent_damage", "value": 7}]},
            "some_shield",
        )
        assert isinstance(trigger.effects[0], PreventDamageEffect)

    def test_the_catalogue_only_uses_it_there(self):

        for item_id, spec in config_loader.items.items():
            for trigger in spec.triggers or []:
                for effect in getattr(trigger, "effects", []) or []:
                    if isinstance(effect, PreventDamageEffect):
                        assert isinstance(trigger, OnAttackedTrigger), item_id

    def test_an_effect_with_no_handler_is_not_skipped_quietly(self):
        """The backstop. An effect the engine cannot apply used to fall
        through the chain and vanish, which is how an item comes to load
        cleanly and do less than it says."""

        item = BattleItem(
            spec=ItemSpec(id="odd", name="Odd", category="defense", cost=1,
                          player_class="neutral", shape=parse_map(["#"], "o"),
                          slug="odd", triggers=[]),
            position=(0, 0), uid="odd",
        )
        sim = BattleSimulator(seed=1)
        with pytest.raises(TypeError, match="PreventDamageEffect"):
            sim._apply_effects([PreventDamageEffect(7)], item, None, None)


class TestABadCatalogueStopsTheServer:
    """It used to log and carry on, losing the rest of the file.

    That was worse than losing everything: items before the bad one survived
    and items after it vanished, so the catalogue was quietly half-loaded and
    the shop sold from whatever was left.
    """

    @staticmethod
    def _catalogue(edit) -> str:
        """A copy of the real catalogue with one thing wrong in it"""
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree("data/items", tmp / "items")
        edit(tmp / "items", json)
        return str(tmp)

    def test_a_bad_item_stops_the_load(self):

        def break_one_debuff(items_dir, json):
            path = items_dir / "problems.json"
            d = json.loads(path.read_text())
            d["items"]["virus_injector"]["triggers"][1]["effects"][0][
                "debuff_name"
            ] = "virus"
            path.write_text(json.dumps(d))

        with pytest.raises(CatalogueError) as raised:
            ConfigLoader(self._catalogue(break_one_debuff)).load_all()

        # The message has to say which file and which item, or a catalogue of
        # 224 items is no use to debug.
        assert "problems.json" in str(raised.value)
        assert "virus_injector" in str(raised.value)

    def test_a_json_typo_stops_the_load(self):
        """A missing bracket in consumables.json once ran the whole game with
        zero consumables and nothing said so."""

        def break_the_json(items_dir, json):
            (items_dir / "patches.json").write_text('{"items": {,}}')

        with pytest.raises(CatalogueError, match="patches.json"):
            ConfigLoader(self._catalogue(break_the_json)).load_all()

    def test_a_missing_catalogue_stops_the_load(self):
        """Containers are read first, so that is what an empty path reports"""
        with pytest.raises(CatalogueError, match="no containers file"):
            ConfigLoader("/nowhere/at/all").load_all()

        with pytest.raises(CatalogueError, match="no items directory"):
            ConfigLoader("/nowhere/at/all").load_items()

    def test_nothing_is_half_loaded(self):
        """The old failure kept whatever it had read before the bad item"""
        def break_one_debuff(items_dir, json):
            path = items_dir / "problems.json"
            d = json.loads(path.read_text())
            d["items"]["virus_injector"]["triggers"][1]["effects"][0][
                "debuff_name"
            ] = "virus"
            path.write_text(json.dumps(d))

        loader = ConfigLoader(self._catalogue(break_one_debuff))
        with pytest.raises(CatalogueError):
            loader.load_all()
        assert loader.items == {}, "a half-read catalogue must not be kept"


class TestTheCatalogueIsFoundFromAnywhere:
    """It used to resolve `data` against the working directory"""
    def test_it_does_not_depend_on_where_the_process_is_running(self):

        here = os.getcwd()
        try:
            os.chdir(tempfile.mkdtemp())
            loader = ConfigLoader()
            loader.load_all()
            assert len(loader.items) > 100
        finally:
            os.chdir(here)

    def test_the_default_sits_next_to_the_module(self):

        assert ConfigLoader.DATA_DIR == Path(config_loader_module.__file__).parent / "data"
class TestTheCatalogueIsOneCatalogue:
    """Every item in every file, read together.

    The files are read from disk rather than through ConfigLoader, which keys
    every item by id in one dict. Two items sharing an id look like one item
    there, so the loader is the wrong place to notice it from: it would report
    one item fewer than the files hold and nothing about which one lost.
    """

    @staticmethod
    def _every_entry():
        """(item_id, config, filename) for items and containers alike."""
        items_dir = Path(__file__).parent.parent / "data" / "items"
        for path in sorted(items_dir.glob("*.json")):
            data = json.loads(path.read_text())
            group = data.get("items", data.get("containers", {}))
            for item_id, config in group.items():
                yield item_id, config, path.name

    def test_there_are_items_to_check(self):
        # A glob that matched nothing would make every test below pass.
        assert len(list(self._every_entry())) > 200

    def test_no_two_items_share_an_id(self):
        """An id is what a purchase and a battle name an item by, so a repeat
        means one of the two is unreachable and nothing says which."""
        seen = {}
        for item_id, _, filename in self._every_entry():
            assert item_id not in seen, (
                f"{item_id} is in both {seen[item_id]} and {filename}"
            )
            seen[item_id] = filename

    def test_no_two_items_share_a_name(self):
        """The name is all a player has to tell two items apart by."""
        seen = {}
        for item_id, config, _ in self._every_entry():
            name = config["name"]
            assert name not in seen, f"{item_id} and {seen[name]} are both {name}"
            seen[name] = item_id

    def test_the_id_and_the_slug_agree(self):
        """item_visual.gd builds res://assets/items/<slug>.png, so a slug that
        disagrees with the id points at a file that cannot be there."""
        for item_id, config, filename in self._every_entry():
            assert config["slug"] == item_id, (
                f"{item_id} in {filename} calls itself {config['slug']}"
            )

    def test_every_item_names_the_item_it_came_from(self):
        """Our numbers are the wiki's. With no source there is nothing to check
        a number against, and the item drifts unnoticed."""
        for item_id, config, filename in self._every_entry():
            assert config.get("source"), f"{item_id} in {filename} has no source"

    def test_every_map_parses(self):

        for item_id, config, _ in self._every_entry():
            parse_map(config["map"], item_id)


class TestEveryItemIsOneASentaurCanReach:
    """Our only class is Sentaur, which is the wiki's Ranger.

    An item whose numbers come from a Berserker or Mage item is one no player
    can ever legitimately own, so it has no business in the catalogue however
    good those numbers are. Three were, and were caught by hand.
    """

    # Ranger is Sentaur. Neutral is open to everyone. An item with no class at
    # all is unrestricted.
    REACHABLE = {"Neutral", "Ranger", ""}

    @staticmethod
    def _wiki():
        """The scrape, or a skip. It is not committed, so a fresh clone has no
        way to check this and should say so rather than pass."""
        import json
        from pathlib import Path

        scrape = (
            Path(__file__).parent.parent.parent
            / "research"
            / "item_grids"
            / "all_item_grids.json"
        )
        if not scrape.exists():
            pytest.skip("research/item_grids/all_item_grids.json is not in this checkout")
        return json.loads(scrape.read_text())

    def test_no_item_comes_from_a_class_we_do_not_have(self):
        wiki = self._wiki()
        unreachable = []
        for item_id, config, _ in TestTheCatalogueIsOneCatalogue._every_entry():
            record = wiki.get(config["source"])
            if record is None:
                continue
            classes = {c.strip() for c in (record.get("class") or "").split(",")}
            if classes & self.REACHABLE:
                continue
            unreachable.append(f"{item_id} <- {config['source']} ({record['class']})")
        assert not unreachable, "\n".join(unreachable)

    def test_a_subclass_item_is_not_offered(self):
        """A Ranger reaches these, but only through a subclass, and subclasses
        are not built. They stay, held back, rather than being deleted."""
        from config_loader import config_loader

        wiki = self._wiki()
        for item_id, config, _ in TestTheCatalogueIsOneCatalogue._every_entry():
            record = wiki.get(config["source"]) or {}
            if not record.get("subclass"):
                continue
            spec = config_loader.items.get(item_id) or config_loader.containers[item_id]
            assert not spec.in_shop, (
                f"{item_id} needs the {record['subclass']} subclass "
                f"and the shop offers it anyway"
            )

class TestCleanseLoading:
    """A cleanse states its count, and names something real or nothing"""
    def loader(self):

        return ConfigLoader()

    def test_a_cleanse_has_to_state_its_count(self):

        with pytest.raises(ValueError, match="count"):
            self.loader()._parse_effect({"type": "cleanse"}, "some_item")

    def test_a_named_cleanse_has_to_name_a_real_debuff(self):
        """`virus` and `corruption` were once written as debuffs. A cleanse
        aimed at one would load cleanly and remove nothing, forever."""

        with pytest.raises(ValueError, match="not something to cleanse"):
            self.loader()._parse_effect(
                {"type": "cleanse", "count": 4, "removes": "virus"}, "some_item"
            )

    def test_a_cleanse_has_to_say_what_it_removes(self):
        """Even taking any debuff is a choice, and the item makes it"""
        with pytest.raises(ValueError, match="removes"):
            self.loader()._parse_effect({"type": "cleanse", "count": 3}, "some_item")

    def test_taking_any_of_a_kind_is_written_out(self):

        effect = self.loader()._parse_effect(
            {"type": "cleanse", "count": 3, "removes": "debuff", "target": "self"},
            "some_item",
        )
        assert isinstance(effect, CleanseEffect)
        assert (effect.count, effect.removes) == (3, "debuff")
        assert effect.named() is False
        assert effect.kind() == "debuff"

    def test_a_named_cleanse_knows_its_own_kind(self):

        effect = self.loader()._parse_effect(
            {"type": "cleanse", "count": 4, "removes": MEMORY_LEAKED, "target": "self"},
            "some_item",
        )
        assert effect.named() is True
        assert effect.kind() == "debuff", "the name says which pool, unaided"

    def test_the_catalogue_only_cleanses_things_that_exist(self):

        found = [
            effect
            for spec in config_loader.items.values()
            for trigger in spec.triggers or []
            for effect in getattr(trigger, "effects", []) or []
            if isinstance(effect, CleanseEffect)
        ]
        assert found, "the catalogue should cleanse somewhere"
        for effect in found:
            assert effect.count > 0
            if effect.named():
                assert effect.removes in BUFFS | DEBUFFS, (
                    "a name says which pool it draws from, so it has to be one"
                )

    def test_health_potion_matches_its_source(self):
        """"Health drops below 50%: Consume this and heal for 12 and cleanse
        4 Poison." All four parts, in one item."""

        (trigger,) = config_loader.items["health_potion"].triggers
        assert isinstance(trigger, HealthThresholdTrigger)
        assert trigger.threshold == 0.5

        by_type = {type(e).__name__: e for e in trigger.effects}
        assert by_type["HealEffect"].min_heal == 12
        assert by_type["HealEffect"].max_heal == 12
        assert by_type["CleanseEffect"].count == 4
        assert by_type["CleanseEffect"].removes == MEMORY_LEAKED
        assert isinstance(by_type["ConsumeEffect"], ConsumeEffect)


class TestABuffIsNotAStat:
    """Section 3.1: seven buffs, and a number on an item is not one of them"""

    def loader(self):
        return ConfigLoader()

    def test_a_stat_written_as_a_buff_is_refused(self):
        """`speed`, `accuracy`, `cpu_cost` and the rest were all filed as
        buffs, and the player carried them where nothing read them."""
        for stat in ["trigger_speed", "accuracy", "cpu_cost", "damage_flat"]:
            with pytest.raises(ValueError, match="modify"):
                self.loader()._parse_effect(
                    {"type": "buff", "stat": stat, "value": 0.1, "target": "self"},
                    "some_item",
                )

    def test_a_buff_nothing_stacks_is_refused(self):
        with pytest.raises(ValueError, match="not a buff"):
            self.loader()._parse_effect(
                {"type": "buff", "buff_name": "immunity", "value": 1,
                 "target": "self"},
                "some_item",
            )

    def test_a_modifier_has_to_change_something_real(self):
        with pytest.raises(ValueError, match="not something an item modifier"):
            self.loader()._parse_effect(
                {"type": "modify", "stat": "morale", "value": 1, "target": "own"},
                "some_item",
            )

    def test_a_modifier_says_what_it_reaches(self):
        for missing in ["value", "target"]:
            config = {"type": "modify", "stat": "trigger_speed",
                      "value": 0.1, "target": "own"}
            del config[missing]
            with pytest.raises(ValueError, match=missing):
                self.loader()._parse_effect(config, "some_item")

    def test_the_catalogue_has_no_stat_left_among_the_buffs(self):
        from item_effects import BUFFS, MODIFIERS, BuffEffect, ModifyEffect

        buffs, modifiers = [], []
        for spec in config_loader.items.values():
            for trigger in spec.triggers or []:
                for effect in getattr(trigger, "effects", []) or []:
                    if isinstance(effect, BuffEffect):
                        buffs.append(effect.buff_name)
                    if isinstance(effect, ModifyEffect):
                        modifiers.append(effect.stat)

        assert buffs and modifiers, "the catalogue should have both"
        assert set(buffs) <= BUFFS
        assert set(modifiers) <= MODIFIERS
        assert not set(buffs) & MODIFIERS, "no stat is filed as a buff"

    def test_a_modifier_reaches_somewhere_real(self):
        """`adjacent` was a scope until adjacency turned out not to be a
        mechanic this game has. An aura zone is drawn on the item's own map."""
        for bad in ["adjacent", "neighbours", "everything"]:
            with pytest.raises(ValueError, match="not somewhere a modifier"):
                self.loader()._parse_effect(
                    {"type": "modify", "stat": "trigger_speed", "value": 0.1,
                     "target": bad, "counting": "any", "cap": None},
                    "some_item",
                )

    def test_gloves_of_haste_reaches_its_star(self):
        """"Start of battle: Star items trigger 20% faster." The aura is drawn
        on the map as `*`, so the effect names that zone rather than guessing
        at what sits nearby."""
        from item_effects import BattleStartTrigger, ModifyEffect

        spec = config_loader.items["load_balancer_module"]
        (trigger,) = spec.triggers
        assert isinstance(trigger, BattleStartTrigger)
        (effect,) = trigger.effects
        assert isinstance(effect, ModifyEffect)
        assert effect.stat == "trigger_speed"
        assert effect.value == 0.2
        assert effect.target_type == "star"

    def test_an_item_reaching_a_zone_actually_draws_one(self):
        """A modifier scoped to an aura is meaningless if the item's map has
        no such zone on it."""
        from item_effects import ModifyEffect

        for item_id, spec in config_loader.items.items():
            for trigger in spec.triggers or []:
                for effect in getattr(trigger, "effects", []) or []:
                    if isinstance(effect, ModifyPerEffect):
                        zones = (spec.shape.star if effect.zone == "star"
                                 else spec.shape.diamond)
                        assert zones, (
                            f"{item_id} counts a {effect.zone} it never draws"
                        )
                    if isinstance(effect, ModifyEffect) and effect.target_type in (
                        "star", "diamond"
                    ):
                        zones = (
                            spec.shape.star
                            if effect.target_type == "star"
                            else spec.shape.diamond
                        )
                        assert zones, (
                            f"{item_id} reaches a {effect.target_type} it never draws"
                        )


class TestWhatTheShopMayOffer:
    """Two fields decide whether an item can be bought at all.

    `recipe_only` says crafting is the only way to get one. `shop_needs` says
    the shop stocks it only while the player holds another item. Both were in
    the catalogue before anything read them, and both were wrong in a way a
    player would have seen: a craft-only item was on sale, and fourteen items
    that wait on a Coin Miner were unreachable with or without one.
    """

    @staticmethod
    def _catalogue():
        import json
        from pathlib import Path

        items_dir = Path(__file__).parent.parent / "data" / "items"
        for path in sorted(items_dir.glob("*.json")):
            data = json.loads(path.read_text())
            for item_id, config in (data.get("items") or data["containers"]).items():
                yield item_id, config

    def test_a_recipe_only_item_is_never_offered(self):
        """Rolled at a round that reaches its rarity.

        Round one offers common and rare only, and the one craft-only item is
        epic, so asking round one proves nothing: it could not turn up whether
        the rule worked or not.
        """
        from config_loader import config_loader
        from main import generate_shop_items

        craft_only = {
            item_id for item_id, config in self._catalogue()
            if config.get("recipe_only")
        }
        assert craft_only, "no item is recipe_only, so this checks nothing"

        rarities = {
            (config_loader.items.get(i) or config_loader.containers[i]).rarity
            for i in craft_only
        }
        offered_rarities, everything = set(), set()
        for seed in range(200):
            for offer in generate_shop_items(8, seed, held=set(craft_only)):
                if offer:
                    everything.add(offer.item_type)
                    offered_rarities.add(offer.rarity.lower())
        assert rarities <= offered_rarities, (
            f"round 8 never offered a {rarities - offered_rarities} item, so this "
            f"says nothing about whether a craft-only one would be"
        )
        assert not (everything & craft_only), f"the shop offered {everything & craft_only}"

    def test_recipe_only_beats_in_shop(self):
        """The two could disagree in the JSON, and one of them has to win."""
        from config_loader import config_loader

        for item_id, config in self._catalogue():
            if config.get("recipe_only"):
                spec = config_loader.items.get(item_id) or config_loader.containers[item_id]
                assert not spec.in_shop, f"{item_id} is craft-only and offered anyway"

    def test_an_item_waiting_on_another_is_offered_only_once_it_is_held(self):
        """The rule, not today's catalogue.

        All fourteen items that wait on a Coin Miner are also `in_shop: false`,
        because their effects are not built. So nothing in the catalogue passes
        both gates yet, and asking the real shop would say nothing about the
        rule. This offers one item and turns the gate on and off.
        """
        from unittest.mock import patch

        from battle_engine import ITEM_CATALOG
        from main import generate_shop_items

        waits_on = "crypto_mining_rig"
        original = ITEM_CATALOG["null_blade"]
        gated = original.__class__(
            **{**original.__dict__, "shop_needs": waits_on}
        )

        with patch.dict(ITEM_CATALOG, {"null_blade": gated}):
            without = set()
            with_it = set()
            for seed in range(120):
                without |= {
                    o.item_type for o in generate_shop_items(1, seed, held=set()) if o
                }
                with_it |= {
                    o.item_type
                    for o in generate_shop_items(1, seed, held={waits_on})
                    if o
                }

        assert "null_blade" not in without, "offered without what it waits on"
        assert "null_blade" in with_it, "not offered even while holding it"

    def test_holding_something_else_does_not_help(self):
        from unittest.mock import patch

        from battle_engine import ITEM_CATALOG
        from main import generate_shop_items

        original = ITEM_CATALOG["null_blade"]
        gated = original.__class__(
            **{**original.__dict__, "shop_needs": "crypto_mining_rig"}
        )
        with patch.dict(ITEM_CATALOG, {"null_blade": gated}):
            offered = set()
            for seed in range(120):
                offered |= {
                    o.item_type
                    for o in generate_shop_items(1, seed, held={"stack_smasher"})
                    if o
                }
        assert "null_blade" not in offered

    def test_the_catalogue_waits_on_items_that_exist(self):
        """A slug that names nothing would gate an item forever."""
        from config_loader import config_loader

        known = set(config_loader.items) | set(config_loader.containers)
        for item_id, config in self._catalogue():
            needed = config.get("shop_needs")
            if needed:
                assert needed in known, f"{item_id} waits on {needed}, which does not exist"


class TestEveryRecipeCouldBeFollowed:
    """A recipe naming an item we do not have can never be completed.

    Not a failure on its own -- Burning Coal needs a Pyromancer's flame and
    there is no Pyromancer -- but it should be a short, known list rather than
    something that quietly grows.
    """

    @staticmethod
    def _recipes():
        for item_id, config in TestWhatTheShopMayOffer._catalogue():
            for recipe in config.get("recipe", []):
                yield item_id, recipe

    def test_there_are_recipes_to_check(self):
        assert len(list(self._recipes())) > 50

    def test_every_part_of_every_recipe_is_something_a_player_can_hold(self):
        """A part is a catalogue slug, or a kind some item is.

        `class:fire` is the only kind asked for, and eight items are on fire
        (GDD 5.4). A recipe wanting an item this game never imported is pruned
        at import rather than left here, because nobody could complete it.
        """
        from inventory_manager import any_of

        gaps = {}
        for item_id, recipe in self._recipes():
            unanswered = [
                part
                for part in recipe["ingredients"] + recipe.get("catalysts", [])
                if not any_of(part)
            ]
            if unanswered:
                gaps[item_id] = unanswered

        assert gaps == {}, f"recipes nobody could ever complete: {gaps}"

    def test_nothing_is_its_own_ingredient(self):
        for item_id, recipe in self._recipes():
            parts = recipe["ingredients"] + recipe.get("catalysts", [])
            assert item_id not in parts, f"{item_id} is made from itself"


class TestTheCatalogueStillSaysWhatTheWikiSays:
    """Every number in the catalogue came from a Backpack Battles page, and
    `research/parse_wiki.py` can read those pages again.

    So nothing has to be trusted. The corpus is committed, the parser is
    committed, and this compares the two. It exists because the catalogue is
    edited by hand on nearly every commit -- adding a trigger, closing a
    clause -- and a stat changed by accident in that traffic would otherwise
    be found by nobody.
    """

    @staticmethod
    def _wiki():
        import importlib.util
        import sys
        from pathlib import Path

        here = Path(__file__).resolve().parents[2] / "research" / "parse_wiki.py"
        spec = importlib.util.spec_from_file_location("parse_wiki", here)
        module = importlib.util.module_from_spec(spec)
        sys.modules["parse_wiki"] = module
        spec.loader.exec_module(module)
        return {page["name"]: page for page in module.parse().values()}

    @staticmethod
    def _number(value):
        """A field as a number, or None where it is not one. The gemstone
        pages give ranges like "1/2/4/8/16", one page covering five tiers."""
        if value in (None, ""):
            return None
        try:
            return float(str(value).strip().rstrip("%"))
        except ValueError:
            return None

    def test_every_stat_matches_the_page_it_came_from(self):
        import json
        from pathlib import Path

        wiki = self._wiki()
        items = Path(__file__).resolve().parents[1] / "data" / "items"
        wrong, checked = [], 0

        for path in sorted(items.glob("*.json")):
            data = json.loads(path.read_text())
            for group in ("items", "containers"):
                for item_id, item in data.get(group, {}).items():
                    page = wiki.get(item.get("source"))
                    if not page:
                        continue
                    checked += 1

                    def same(field, ours, theirs, scale=1):
                        a, b = self._number(ours), self._number(theirs)
                        if a is None or b is None:
                            return
                        if a != round(b * scale, 4):
                            wrong.append(f"{item_id}.{field}: {a} vs {b * scale}")

                    same("cost", item.get("cost"), page.get("cost"))
                    same("sockets", item.get("sockets"), page.get("sockets"))
                    for trigger in item.get("triggers") or []:
                        for effect in trigger.get("effects") or []:
                            if effect.get("type") == "attack":
                                same("min_damage", effect.get("min_damage"),
                                     page.get("mindamage"))
                                same("max_damage", effect.get("max_damage"),
                                     page.get("maxdamage"))
                                same("accuracy", effect.get("accuracy"),
                                     page.get("accuracy"), 0.01)
                        if trigger.get("type") == "timer":
                            same("cooldown", trigger.get("cooldown"),
                                 page.get("cooldown"))
                            same("cpu_cost", trigger.get("cpu_cost"),
                                 page.get("stamina"))

        assert checked > 200, f"only {checked} items could be checked"
        assert not wrong, "\n".join(wrong)

    def test_rarity_matches_except_where_one_page_covers_five_tiers(self):
        """A gemstone's page says "Varies": it is one page for the chipped,
        flawed, regular, flawless and perfect cuts, and the catalogue names
        which of them each item is."""
        import json
        from pathlib import Path

        wiki = self._wiki()
        items = Path(__file__).resolve().parents[1] / "data" / "items"
        wrong = []
        for path in sorted(items.glob("*.json")):
            data = json.loads(path.read_text())
            for group in ("items", "containers"):
                for item_id, item in data.get(group, {}).items():
                    page = wiki.get(item.get("source"))
                    if not page or not page.get("rarity"):
                        continue
                    theirs = page["rarity"].lower()
                    if theirs == "varies":
                        assert item.get("category") == "module", (
                            f"{item_id} is not a module, so its page should "
                            f"name one rarity"
                        )
                        continue
                    if item.get("rarity", "").lower() != theirs:
                        wrong.append(f"{item_id}: {item.get('rarity')} vs {theirs}")
        assert not wrong, "\n".join(wrong)
