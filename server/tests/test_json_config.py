#!/usr/bin/env python3
"""
Test that JSON configuration system works correctly
"""

from battle_engine import BattleItem, BattleSimulator
from config_loader import ConfigLoader
from containers import Container


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
    core_dumper = loader.get_item("core_dumper")
    loader.get_item("firewall")  # Verify it exists
    health_check = loader.get_item("health_check")

    # Room for the shapes these items actually have. A Core Dumper is a four
    # square L, so a 2x2 container holds it and nothing else.
    p1_container = Container.of("mesh_network_hub", (0, 0), "p1_hub")
    p2_container = Container.of("mesh_network_hub", (4, 0), "p2_hub")

    p1_items = [
        BattleItem(spec=null_blade, position=(0, 0), uid="p1_null"),
        BattleItem(spec=core_dumper, position=(1, 0), uid="p1_leak"),
    ]
    p2_items = [
        BattleItem(spec=core_dumper, position=(4, 0), uid="p2_null2"),
        BattleItem(spec=health_check, position=(5, 1), uid="p2_health"),
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
        from config_loader import config_loader

        spec = config_loader.items["null_blade"]
        assert spec.in_shop is True

    def test_the_shop_skips_an_item_that_is_not_offered(self):
        # Items arrive from Backpack Battles with numbers and no behaviour.
        # They have to be able to sit in the catalogue without a player
        # being able to buy one.
        from unittest.mock import patch

        from battle_engine import ITEM_CATALOG
        from main import generate_shop_items

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
        import json
        from pathlib import Path

        path = Path(__file__).parent.parent / "data" / "unavailable_items.json"
        return json.loads(path.read_text())

    def test_it_sits_outside_the_directory_the_loader_reads(self):
        """ConfigLoader globs data/items/*.json. A file in there is loaded, so
        this one has to be a sibling of that directory rather than inside it."""
        from pathlib import Path

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
        from config_loader import config_loader

        loaded = set(config_loader.items) | set(config_loader.containers)
        clashes = sorted(set(self._set_aside()["items"]) & loaded)
        assert not clashes, f"{clashes} are set aside and loaded anyway"

    def test_the_shop_never_offers_one(self):
        from main import generate_shop_items

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
        from config_loader import config_loader
        from item_effects import AttackEffect, OnHitTrigger, TimerTrigger

        spec = config_loader.items["virus_injector"]
        timer, on_hit = spec.triggers

        assert isinstance(timer, TimerTrigger)
        assert timer.cooldown == 1.7
        assert timer.cpu_cost == 0.7
        attack = timer.effects[0]
        assert isinstance(attack, AttackEffect)
        assert (attack.min_damage, attack.max_damage) == (4, 11)
        assert attack.accuracy == 0.85

        # "On hit: 70% chance to inflict 2 Poison"
        assert isinstance(on_hit, OnHitTrigger)
        assert on_hit.chance == 0.7

    def test_the_debuff_effect_is_not_dropped(self):
        """The loader had no debuff branch, so every debuff in the
        catalogue was silently thrown away at startup"""
        from config_loader import config_loader
        from item_effects import DebuffEffect

        (debuff,) = config_loader.items["virus_injector"].triggers[1].effects
        assert isinstance(debuff, DebuffEffect)
        assert debuff.debuff_name == "memory_leaked"
        assert debuff.value == 2

    def test_the_debuff_never_wears_off(self):
        """Section 3.2: a debuff lasts to the end of the battle"""
        from config_loader import config_loader

        (debuff,) = config_loader.items["virus_injector"].triggers[1].effects
        assert debuff.duration == -1

    def test_the_engine_reads_the_name_the_catalogue_writes(self):
        """The engine pays poison out by name. A disagreement between the two
        spellings would tick nothing, and nothing would say so."""
        from battle_engine import MEMORY_LEAKED
        from config_loader import config_loader

        (debuff,) = config_loader.items["virus_injector"].triggers[1].effects
        assert debuff.debuff_name == MEMORY_LEAKED


class TestCatalogueStrictness:
    """A wrong item should fail loudly, not quietly do nothing"""

    def loader(self):
        from config_loader import ConfigLoader

        return ConfigLoader()

    def test_an_on_hit_trigger_has_to_state_its_chance(self):
        """Both forms exist in the source game -- the Axe is a flat "On hit:
        gain 1 damage", the Torch a "25% chance" -- so a missing chance cannot
        be told apart from an import that lost one."""
        import pytest

        with pytest.raises(ValueError, match="chance"):
            self.loader()._parse_trigger(
                {"type": "on_hit", "effects": []}, "some_item"
            )

    def test_an_always_on_effect_writes_one(self):
        from item_effects import OnHitTrigger

        trigger = self.loader()._parse_trigger(
            {"type": "on_hit", "chance": 1.0, "effects": []}, "some_item"
        )
        assert isinstance(trigger, OnHitTrigger)
        assert trigger.chance == 1.0

    def test_a_debuff_nothing_ticks_is_refused(self):
        """`virus` and `corruption` were both in the catalogue. Neither is a
        debuff, so both were carried on the player and read by nothing, which
        looks exactly like a working debuff until you check the damage."""
        import pytest

        for invented in ["virus", "corruption", "slow", "speed"]:
            with pytest.raises(ValueError, match="not a debuff"):
                self.loader()._parse_effect(
                    {"type": "debuff", "debuff_name": invented, "value": 1},
                    "some_item",
                )

    def test_the_error_names_the_item(self):
        """A catalogue of 95 items is no use to debug without the name"""
        import pytest

        with pytest.raises(ValueError, match="prize_item"):
            self.loader()._parse_effect(
                {"type": "debuff", "debuff_name": "virus"}, "prize_item"
            )

    def test_stat_is_no_longer_a_way_to_name_a_debuff(self):
        """One key. Two spellings is how "speed" became a debuff."""
        import pytest

        with pytest.raises(ValueError, match="not a debuff"):
            self.loader()._parse_effect(
                {"type": "debuff", "stat": "speed", "value": -0.2}, "some_item"
            )

    def test_every_debuff_in_the_catalogue_is_one_the_engine_ticks(self):
        """The catalogue is imported by hand from a wiki, so this is the
        check that the whole of it survived the import."""
        from config_loader import config_loader
        from item_effects import DEBUFFS, DebuffEffect

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
        from config_loader import config_loader
        from item_effects import OnAttackedTrigger

        (trigger,) = [
            t
            for t in config_loader.items[item_id].triggers
            if isinstance(t, OnAttackedTrigger)
        ]
        return trigger

    def test_each_shield_has_its_own_numbers(self):
        from item_effects import CpuDrainEffect, PreventDamageEffect

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
        import pytest

        from config_loader import ConfigLoader

        with pytest.raises(ValueError, match="chance"):
            ConfigLoader()._parse_trigger(
                {"type": "on_attacked", "effects": []}, "some_shield"
            )

    def test_both_effects_have_to_state_a_value(self):
        """No defaults. A number that never arrived would otherwise load as a
        working shield."""
        import pytest

        from config_loader import ConfigLoader

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
        import pytest

        from config_loader import ConfigLoader

        block = {"type": "prevent_damage", "value": 7}
        for trigger in ["timer", "battle_start", "passive", "damage_taken"]:
            with pytest.raises(ValueError, match="on_attacked"):
                ConfigLoader()._parse_trigger(
                    {"type": trigger, "chance": 1.0, "cooldown": 1.0,
                     "effects": [block]},
                    "some_item",
                )

    def test_it_is_allowed_in_on_attacked(self):
        from config_loader import ConfigLoader
        from item_effects import PreventDamageEffect

        trigger = ConfigLoader()._parse_trigger(
            {"type": "on_attacked", "chance": 0.3,
             "effects": [{"type": "prevent_damage", "value": 7}]},
            "some_shield",
        )
        assert isinstance(trigger.effects[0], PreventDamageEffect)

    def test_the_catalogue_only_uses_it_there(self):
        from config_loader import config_loader
        from item_effects import OnAttackedTrigger, PreventDamageEffect

        for item_id, spec in config_loader.items.items():
            for trigger in spec.triggers or []:
                for effect in getattr(trigger, "effects", []) or []:
                    if isinstance(effect, PreventDamageEffect):
                        assert isinstance(trigger, OnAttackedTrigger), item_id

    def test_an_effect_with_no_handler_is_not_skipped_quietly(self):
        """The backstop. An effect the engine cannot apply used to fall
        through the chain and vanish, which is how an item comes to load
        cleanly and do less than it says."""
        import pytest

        from battle_engine import BattleItem, BattleSimulator
        from grid_system import parse_map
        from item_effects import ItemSpec, PreventDamageEffect

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
        import json
        import shutil
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp())
        shutil.copytree("data/items", tmp / "items")
        edit(tmp / "items", json)
        return str(tmp)

    def test_a_bad_item_stops_the_load(self):
        import pytest

        from config_loader import CatalogueError, ConfigLoader

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
        import pytest

        from config_loader import CatalogueError, ConfigLoader

        def break_the_json(items_dir, json):
            (items_dir / "patches.json").write_text('{"items": {,}}')

        with pytest.raises(CatalogueError, match="patches.json"):
            ConfigLoader(self._catalogue(break_the_json)).load_all()

    def test_a_missing_catalogue_stops_the_load(self):
        """Containers are read first, so that is what an empty path reports"""
        import pytest

        from config_loader import CatalogueError, ConfigLoader

        with pytest.raises(CatalogueError, match="no containers file"):
            ConfigLoader("/nowhere/at/all").load_all()

        with pytest.raises(CatalogueError, match="no items directory"):
            ConfigLoader("/nowhere/at/all").load_items()

    def test_nothing_is_half_loaded(self):
        """The old failure kept whatever it had read before the bad item"""
        import pytest

        from config_loader import CatalogueError, ConfigLoader

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
        import os
        import tempfile

        from config_loader import ConfigLoader

        here = os.getcwd()
        try:
            os.chdir(tempfile.mkdtemp())
            loader = ConfigLoader()
            loader.load_all()
            assert len(loader.items) > 100
        finally:
            os.chdir(here)

    def test_the_default_sits_next_to_the_module(self):
        from pathlib import Path

        import config_loader as module
        from config_loader import ConfigLoader

        assert ConfigLoader.DATA_DIR == Path(module.__file__).parent / "data"
