"""What an item does, in words, built from what it actually does."""

import re
from copy import deepcopy

import describe
from battle_engine import ITEM_CATALOG
from item_effects import (
    AttackEffect,
    BattleStartTrigger,
    BuffEffect,
    ChanceEffect,
    CleanseEffect,
    ConditionEffect,
    CpuDrainEffect,
    DebuffEffect,
    LimitEffect,
    ModifyEffect,
    ModifyPerStatusEffect,
    OnAttackedTrigger,
    OnHitTrigger,
    PassiveTrigger,
    PlayerModifyEffect,
    RandomStatusEffect,
    ReflectEffect,
    ResistEffect,
    StunEffect,
    TimerTrigger,
)

#: What the server marks a status with, so the client can pick it out in a
#: colour. Taken back out where a test is about the words rather than the
#: marks; there is a test of its own for those.
MARK = re.compile(r"\[/?(buff|debuff|star|diamond)\]")


def plain(text: str) -> str:
    """A line as the words in it, with the marks around the statuses taken off"""
    return MARK.sub("", text)


def block(trigger) -> list:
    return [plain(one) for one in describe.block(trigger)]


def line(trigger) -> str:
    """The one line a trigger that does one thing comes to"""
    said = describe.block(trigger)
    assert len(said) == 1, said
    return plain(said[0])


class TestWhatAnEffectSays:
    def test_a_weapon_says_what_it_hits_for_and_what_it_costs(self):
        assert (
            line(
                TimerTrigger(
                    cooldown=1.4,
                    cpu_cost=1.0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=3, accuracy=0.85, crit_chance=0.05
                        )
                    ],
                )
            )
            == "Every 1.4s (1 CPU): deal 1-3 damage"
        )

    def test_one_number_rather_than_a_range_that_does_not_vary(self):
        assert "deal 5 damage" in line(
            TimerTrigger(
                cooldown=2,
                cpu_cost=0,
                effects=[
                    AttackEffect(
                        min_damage=5, max_damage=5, accuracy=0.85, crit_chance=0.05
                    )
                ],
            )
        )

    def test_a_status_is_named_as_a_player_reads_it(self):
        # The catalogue knows them as identifiers. "Apply 2 memory_leaked" is
        # a tooltip written for whoever wrote the catalogue.
        said = line(
            OnHitTrigger(
                chance=1.0, effects=[DebuffEffect(debuff_name="memory_leaked", value=2)]
            )
        )
        assert said == "On hit: apply 2 memory leak to your opponent"

    def test_the_odds_go_in_front_of_the_whole_clause(self):
        # The source game writes them that way, because one roll decides all
        # of it: the damage cannot land while the buff does not.
        said = line(
            OnHitTrigger(
                chance=1.0,
                effects=[
                    ChanceEffect(
                        chance=0.25,
                        effects=[
                            BuffEffect(buff_name="spiked", value=1, target_type="self"),
                            AttackEffect(
                                min_damage=2,
                                max_damage=2,
                                accuracy=0.85,
                                crit_chance=0.05,
                            ),
                        ],
                    )
                ],
            )
        )
        assert said == "On hit: 25% chance to gain 1 spiked and deal 2 damage"

    def test_a_run_of_buffs_is_said_once(self):
        # An item granting seven of them is written as seven effects, and read
        # back one at a time it is a line nobody finishes.
        said = line(
            TimerTrigger(
                cooldown=8,
                cpu_cost=0,
                effects=[
                    BuffEffect(buff_name="optimized", value=1, target_type="self"),
                    BuffEffect(buff_name="spiked", value=1, target_type="self"),
                    BuffEffect(buff_name="credits", value=1, target_type="self"),
                ],
            )
        )
        assert said == "Every 8s: gain 1 optimised, spiked and credits"

    def test_the_three_weapon_kinds_are_just_weapons(self):
        said = line(
            BattleStartTrigger(
                effects=[
                    ModifyEffect(
                        stat="damage",
                        value=0.15,
                        target_type="star",
                        cap=None,
                        counting={"any": ["melee", "ranged", "magic"]},
                        duration=-1,
                    )
                ]
            )
        )
        assert said == "Battle start: star weapons get +15% damage"

    def test_tags_an_item_might_carry_are_alternatives(self):
        # `any` means an item carrying one of them. Joined with "and" it reads
        # as a single item that is somehow both.
        said = line(
            BattleStartTrigger(
                effects=[
                    ModifyEffect(
                        stat="trigger_speed",
                        value=0.1,
                        target_type="star",
                        cap=None,
                        counting={"any": ["pet", "script"]},
                        duration=-1,
                    )
                ]
            )
        )
        assert "pet or script star items" in said

    def test_a_condition_carries_both_halves(self):
        said = line(
            TimerTrigger(
                cooldown=1.3,
                cpu_cost=0,
                effects=[
                    ConditionEffect(
                        subject="status",
                        whose="enemy",
                        status="throttled",
                        test="at_least",
                        amount=10,
                        effects=[
                            BuffEffect(
                                buff_name="monitored", value=1, target_type="self"
                            )
                        ],
                        otherwise=[DebuffEffect(debuff_name="throttled", value=1)],
                    )
                ],
            )
        )
        assert said == (
            "Every 1.3s: if your opponent has at least 10 throttled, gain 1 "
            "monitored; otherwise apply 1 throttled to your opponent"
        )

    def test_taking_a_status_off_says_who_it_comes_off(self):
        assert "cleanse 2 memory leak from yourself" in line(
            TimerTrigger(
                cooldown=2,
                cpu_cost=0,
                effects=[
                    CleanseEffect(count=2, removes="memory_leaked", target_type="self")
                ],
            )
        )
        assert "remove 1 buff from your opponent" in line(
            TimerTrigger(
                cooldown=2,
                cpu_cost=0,
                effects=[CleanseEffect(count=1, removes="buff", target_type="enemy")],
            )
        )

    def test_something_always_true_says_only_what_it_does(self):
        # A passive has no condition, so a line beginning "always:" would be
        # a word doing no work.
        said = line(
            PassiveTrigger(
                effects=[
                    ModifyEffect(
                        stat="trigger_speed",
                        value=-0.3,
                        target_type="star",
                        cap=None,
                        counting="any",
                        duration=-1,
                    )
                ]
            )
        )
        assert said == "Star items get -30% trigger speed"

    def test_a_status_nobody_chose_has_an_article(self):
        assert "gain a random buff" in line(
            TimerTrigger(
                cooldown=2,
                cpu_cost=0,
                effects=[RandomStatusEffect(kind="buff", count=1, target_type="self")],
            )
        )
        assert "inflict 3 random debuffs" in line(
            TimerTrigger(
                cooldown=2,
                cpu_cost=0,
                effects=[
                    RandomStatusEffect(kind="debuff", count=3, target_type="enemy")
                ],
            )
        )

    def test_a_number_on_a_player_reads_as_a_sentence(self):
        # "Your damage taken -25% for 5s" is a stat line, and these sit in the
        # middle of a sentence.
        said = line(
            BattleStartTrigger(
                effects=[
                    PlayerModifyEffect(
                        stat="damage_taken",
                        value=-0.25,
                        target_type="self",
                        duration=5.0,
                    )
                ]
            )
        )
        assert said == ("Battle start: your damage taken is reduced by 25% for 5s")

    def test_refusing_a_debuff_says_which_way_it_is_refused(self):
        assert "refuse the next 2 debuffs" in line(
            BattleStartTrigger(
                effects=[ResistEffect(count=2, chance=0, target_type="self")]
            )
        )
        assert "refuse a debuff 30% of the time" in line(
            BattleStartTrigger(
                effects=[ResistEffect(count=0, chance=0.3, target_type="self")]
            )
        )

    def test_statuses_taken_off_the_same_person_say_so_once(self):
        said = line(
            TimerTrigger(
                cooldown=4,
                cpu_cost=0,
                effects=[
                    CleanseEffect(count=1, removes="spiked", target_type="enemy"),
                    CleanseEffect(count=2, removes="monitored", target_type="enemy"),
                ],
            )
        )
        assert said == "Every 4s: remove 1 spiked and 2 monitored from your opponent"

    def test_a_flat_bonus_is_not_said_as_a_percentage(self):
        # `damage` scales what a weapon rolls and `damage_flat` adds to it.
        # Read the same way, a +1 became "+100% damage".
        flat = line(
            PassiveTrigger(
                effects=[
                    ModifyPerStatusEffect(
                        stat="damage_flat", value=1.0, status="spiked", whose="self"
                    )
                ]
            )
        )
        scaled = line(
            PassiveTrigger(
                effects=[
                    ModifyPerStatusEffect(
                        stat="damage", value=0.15, status="spiked", whose="self"
                    )
                ]
            )
        )

        assert flat == "+1 damage for each spiked you have"
        assert scaled == "+15% damage for each spiked you have"


class TestWhoItLandsOn:
    """The engine reads one word, `self`, and takes anything else as the
    other player. A description that reads it any less literally names the
    wrong fighter -- which is how a shield draining its attacker came to say
    the shield's owner was paying the CPU.
    """

    def test_cpu_taken_off_the_attacker_comes_off_your_opponent(self):
        said = line(
            OnAttackedTrigger(
                chance=0.3,
                answers_to=frozenset({"melee"}),
                effects=[CpuDrainEffect(amount=0.3, target_type="attacker")],
            )
        )
        assert said == ("When attacked (Melee, 30%): drain 0.3 CPU from your opponent")

    def test_cpu_taken_off_yourself_is_what_the_item_cost(self):
        said = line(
            OnAttackedTrigger(
                chance=0.3, effects=[CpuDrainEffect(amount=0.3, target_type="self")]
            )
        )
        assert said == "When attacked (30%): spend 0.3 CPU"

    def test_anything_that_is_not_yourself_is_your_opponent(self):
        # Each of these lands on the other player in the engine, whatever word
        # the catalogue used, so each has to say so.
        for effect, expected in [
            (
                StunEffect(duration=1.0, target_type="attacker"),
                "stun your opponent for 1s",
            ),
            (
                ReflectEffect(count=2, target_type="attacker"),
                "make your opponent turn back the next 2 debuffs sent to them",
            ),
            (
                ResistEffect(count=2, chance=0, target_type="attacker"),
                "your opponent refuses the next 2 debuffs",
            ),
            (
                RandomStatusEffect(kind="debuff", count=1, target_type="attacker"),
                "inflict a random debuff",
            ),
            (
                CleanseEffect(count=1, removes="buff", target_type="attacker"),
                "remove 1 buff from your opponent",
            ),
            (
                PlayerModifyEffect(
                    stat="healing_taken",
                    value=-0.3,
                    target_type="attacker",
                    duration=-1,
                ),
                "your opponent's healing received is reduced by 30%",
            ),
            (
                DebuffEffect(debuff_name="throttled", value=1, target_type="attacker"),
                "apply 1 throttled to your opponent",
            ),
        ]:
            assert plain(describe.of_effect(effect)) == expected

    def test_a_buff_is_the_one_that_reads_the_other_way(self):
        # The engine gives a buff to its owner unless it is named for the
        # enemy, so an unfamiliar word means "you" here and "them" above.
        assert (
            plain(
                describe.of_effect(
                    BuffEffect(buff_name="spiked", value=1, target_type="attacker")
                )
            )
            == "gain 1 spiked"
        )
        assert (
            plain(
                describe.of_effect(
                    BuffEffect(buff_name="spiked", value=1, target_type="enemy")
                )
            )
            == "give your opponent 1 spiked"
        )


class TestHowALineIsLaidOut:
    def test_a_trigger_that_does_several_things_lists_them(self):
        assert block(
            OnAttackedTrigger(
                chance=0.3,
                answers_to=frozenset({"melee"}),
                effects=[
                    describe.PreventDamageEffect(amount=7),
                    CpuDrainEffect(amount=0.3, target_type="attacker"),
                ],
            )
        ) == [
            "When attacked (Melee, 30%):",
            "• Prevent 7 damage",
            "• Drain 0.3 CPU from your opponent",
        ]

    def test_a_trigger_that_does_one_thing_stays_one_line(self):
        # A heading over a list of one is a list for the sake of it.
        assert (
            len(
                block(
                    TimerTrigger(
                        cooldown=2,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=2,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                )
            )
            == 1
        )

    def test_standing_clauses_carry_no_bullet(self):
        # A bullet says "part of what the line above asks for", and a passive
        # has no line above it.
        said = block(
            PassiveTrigger(
                effects=[
                    ModifyPerStatusEffect(
                        stat="damage_flat", value=1, status="spiked", whose="self"
                    ),
                    ModifyPerStatusEffect(
                        stat="damage_flat", value=1, status="draining", whose="self"
                    ),
                ]
            )
        )
        assert said == [
            "+1 damage for each spiked you have",
            "+1 damage for each draining you have",
        ]

    def test_a_cap_over_everything_goes_up_with_the_condition(self):
        said = block(
            OnHitTrigger(
                chance=1.0,
                effects=[
                    LimitEffect(
                        times=5,
                        effects=[
                            BuffEffect(buff_name="spiked", value=1, target_type="self"),
                            describe.BlockEffect(block_amount=15),
                        ],
                    )
                ],
            )
        )
        assert said == [
            "On hit (up to 5 times):",
            "• Gain 1 spiked",
            "• Gain 15 Block",
        ]

    def test_a_cap_on_one_clause_of_several_stays_with_it(self):
        said = block(
            OnHitTrigger(
                chance=1.0,
                effects=[
                    describe.PreventDamageEffect(amount=4),
                    LimitEffect(
                        times=5,
                        effects=[
                            BuffEffect(buff_name="spiked", value=1, target_type="self")
                        ],
                    ),
                ],
            )
        )
        assert said[-1] == "• Gain 1 spiked (up to 5 times)"

    def test_a_condition_that_can_only_come_round_once_says_it_once(self):
        # "The first time your quota falls below 70% (once)" counts to one
        # twice.
        said = block(
            describe.HealthThresholdTrigger(
                threshold=0.7,
                effects=[
                    LimitEffect(
                        times=1,
                        effects=[
                            BuffEffect(buff_name="spiked", value=1, target_type="self"),
                            describe.BlockEffect(block_amount=15),
                        ],
                    )
                ],
            )
        )
        assert said[0] == "First time below 70% quota:"


class TestTheOrderTheyComeIn:
    def test_the_catalogue_order_is_not_the_reading_order(self):
        # The order the triggers are written in is nobody's decision -- it is
        # the order somebody typed them -- so two items built the same way
        # read differently and a player cannot learn where to look.
        spec = deepcopy(ITEM_CATALOG["null_blade"])
        spec.triggers = [
            PassiveTrigger(
                effects=[
                    ModifyPerStatusEffect(
                        stat="damage_flat", value=1, status="spiked", whose="self"
                    )
                ]
            ),
            OnHitTrigger(
                chance=1.0,
                effects=[BuffEffect(buff_name="spiked", value=1, target_type="self")],
            ),
            TimerTrigger(
                cooldown=2, cpu_cost=0, effects=[describe.BlockEffect(block_amount=5)]
            ),
            BattleStartTrigger(
                effects=[BuffEffect(buff_name="credits", value=1, target_type="self")]
            ),
        ]

        assert [plain(one) for one in describe.lines(spec)] == [
            "Battle start: gain 1 credits",
            "Every 2s: gain 5 Block",
            "On hit: gain 1 spiked",
            "+1 damage for each spiked you have",
        ]

    def test_two_of_a_kind_keep_the_order_they_were_written_in(self):
        # There is nothing to choose between them, and a sort that moved them
        # about would say something the catalogue did not.
        spec = deepcopy(ITEM_CATALOG["null_blade"])
        spec.triggers = [
            TimerTrigger(
                cooldown=4, cpu_cost=0, effects=[describe.BlockEffect(block_amount=3)]
            ),
            TimerTrigger(
                cooldown=4, cpu_cost=0, effects=[describe.BlockEffect(block_amount=9)]
            ),
        ]

        assert describe.lines(spec) == [
            "Every 4s: gain 3 Block",
            "Every 4s: gain 9 Block",
        ]

    def test_every_kind_of_trigger_has_a_place_in_the_order(self):
        # One missing would sit silently at the end, behind the passives.
        import item_effects

        kinds = {
            kind
            for kind in vars(item_effects).values()
            if isinstance(kind, type) and issubclass(kind, describe.Trigger)
        }
        # A kind another one extends is a shape rather than a trigger: nothing
        # in the catalogue loads as a bare Trigger or ChanceTrigger, and
        # neither answers to an event of its own.
        kinds -= {base for kind in kinds for base in kind.__mro__[1:]}
        placed = {
            kind
            for kind in kinds
            if any(issubclass(kind, one) for one in describe.ORDER)
        }

        assert kinds - placed == set()


class TestTheWholeCatalogue:
    def test_every_item_with_behaviour_says_something(self):
        # The words are built from the effects, so an item that does something
        # and says nothing means an effect nobody has written a line for.
        silent = [
            key
            for key, spec in ITEM_CATALOG.items()
            if spec.triggers and not describe.lines(spec)
        ]
        assert silent == []

    def test_every_trigger_in_the_catalogue_says_when_it_happens(self):
        # A trigger nobody has written words for says nothing at all, and its
        # effects then read as things that simply happen: "deal 5 damage",
        # with no "when your opponent is stunned" in front of them. Which is
        # worse than terse, and is what arrives with each new kind of trigger.
        for key, spec in ITEM_CATALOG.items():
            for trigger in spec.triggers or []:
                if isinstance(trigger, PassiveTrigger):
                    continue  # A passive has no condition to say.
                assert describe.of_trigger(trigger), f"{key}: {trigger}"

    def test_an_item_is_used_up_after_it_has_done_what_it_does(self):
        # The catalogue writes the effects in whatever order, and one of them
        # read "it is used up, cleanse 10 debuffs from yourself".
        for key, spec in ITEM_CATALOG.items():
            said = describe.lines(spec)
            for index, one in enumerate(said):
                if "used up" in one:
                    assert index == len(said) - 1 or said[index + 1].endswith(
                        ":"
                    ), f"{key}: {said}"

    def test_no_line_leaks_an_identifier(self):
        # Underscores are what the catalogue writes, not what a player reads.
        for key, spec in ITEM_CATALOG.items():
            for said in describe.lines(spec):
                assert "_" not in said, f"{key}: {said}"

    def test_the_name_the_battle_log_uses_carries_no_marks(self):
        # `shown` is also what the engine stamps on a battle action, for the
        # log and the chips beside each fighter. Both are drawn as plain text,
        # and a mark left in one of them reads back as a mark.
        assert describe.shown("memory_leaked") == "memory leak"
        for status in describe.SHOWN:
            assert "[" not in describe.shown(status), status

    def test_every_status_is_marked_as_the_kind_of_status_it_is(self):
        # The client colours them and knows nothing about what any of them
        # means, so the mark is the only thing telling a buff from a debuff.
        said = describe.block(
            OnHitTrigger(
                chance=1.0,
                effects=[
                    BuffEffect(buff_name="spiked", value=1, target_type="self"),
                    DebuffEffect(debuff_name="throttled", value=2),
                ],
            )
        )

        assert said[1] == "• Gain 1 [buff]spiked[/buff]"
        assert said[2] == ("• Apply 2 [debuff]throttled[/debuff] to your opponent")

    def test_nothing_but_a_mark_carries_a_bracket(self):
        # The card draws these lines as rich text, where a bracket opens a tag
        # and whatever it swallows is never seen. Only the four marks may use
        # one, so a name or a catalogue tag that grows a bracket is caught
        # here rather than by a word going missing on screen.
        for key, spec in ITEM_CATALOG.items():
            for said in describe.lines(spec):
                assert plain(said).count("[") == 0, f"{key}: {said}"
                assert plain(said).count("]") == 0, f"{key}: {said}"

    def test_no_line_is_left_holding_half_a_mark(self):
        for key, spec in ITEM_CATALOG.items():
            for said in describe.lines(spec):
                for mark in ("buff", "debuff", "star", "diamond"):
                    assert said.count(f"[{mark}]") == said.count(f"[/{mark}]"), said

    def test_a_zone_is_marked_as_the_one_of_the_two_it_is(self):
        # The board draws a star zone and a diamond zone differently, and a
        # line naming one has to say which, or a player cannot tell which of
        # the shapes on their own grid the words are about.
        for key, spec in ITEM_CATALOG.items():
            for said in describe.lines(spec):
                for one in describe.ZONES:
                    plain_said = plain(said)
                    if f" {one} item" in plain_said or plain_said.startswith(one):
                        assert f"[{one}]" in said, f"{key}: {said}"

    def test_no_line_starts_mid_sentence(self):
        # Not every line starts with a letter -- a modifier opens with its
        # sign, "+50% trigger speed..." -- so what is checked is that none of
        # them start with a lower-case word.
        for key, spec in ITEM_CATALOG.items():
            for said in describe.lines(spec):
                first = plain(said)
                first = first[2:] if first.startswith("• ") else first
                assert not first[0].islower(), f"{key}: {said}"

    def test_a_list_always_has_something_above_it_to_belong_to(self):
        for key, spec in ITEM_CATALOG.items():
            said = describe.lines(spec)
            for index, one in enumerate(said):
                if one.startswith("• "):
                    assert index > 0, f"{key}: {said}"
                    above = said[index - 1]
                    assert above.endswith(":") or above.startswith(
                        "• "
                    ), f"{key}: {said}"

    def test_an_item_carries_its_lines_to_the_client(self):
        from items import Item

        # Not the damage line: the card puts damage, cooldown and CPU in rows
        # of their own, and that line is all three of them again.
        assert Item.of("poison_dagger", "x").effects == [
            "On hit: apply 2 [debuff]memory leak[/debuff] to your opponent",
            "When your opponent is stunned: attack again",
        ]

    def test_an_item_the_catalogue_gives_no_behaviour_says_nothing(self):
        spec = deepcopy(ITEM_CATALOG["null_blade"])
        spec.triggers = []

        assert describe.lines(spec) == []


class TestWordsForContainersConversionsAndProtection:
    """The words for what a bag holds, what a price buys, and what is kept.

    Each is a shape a player has not read before, and each one had a first
    draft that came out as English nobody would write: "Star items get +30%
    the Block it gives", "Protect buff of your from being taken".
    """

    def _said(self, item_id):
        return describe.lines(ITEM_CATALOG[item_id])

    def test_a_container_says_inside_rather_than_naming_a_zone(self):
        # "for each neutral contained item" is the shape the zones use and is
        # not how any clause about a bag is written.
        assert self._said("container_orchestrator") == [
            "Battle start: gain 8 Block for each neutral item inside"
        ]

    def test_a_scaled_aura_says_who_gets_it_and_what_sizes_it(self):
        assert self._said("network_cache") == [
            "The items it holds get +10% critical chance",
            "The items it holds get +3% critical chance for each "
            "[buff]compute[/buff] you have",
        ]

    def test_a_share_on_what_an_item_gives_says_give_not_get(self):
        assert "[star]Star[/star] items give +30% Block" in self._said(
            "shield_of_valor"
        )

    def test_a_counter_narrowed_to_a_zone_says_whose_giving_it_counts(self):
        assert (
            "Once [star]star[/star] items have given 12 Block: gain 1 "
            "[buff]credits[/buff]" in self._said("moon_shield")
        )

    def test_a_conversion_says_what_it_costs_and_what_it_buys(self):
        assert self._said("vampiric_armor") == [
            "Battle start:",
            "• Turn 50 quota into 100 Block",
            "• Gain 5 [buff]draining[/buff]",
            "Every 2.8s: turn 10 quota into 20 Block",
        ]

    def test_block_from_missing_health_says_what_it_is_a_share_of(self):
        assert (
            "First time below 50% quota: gain Block equal to 40% of your "
            "missing quota" in self._said("stone_armor")
        )

    def test_a_protecting_chance_reads_as_keeping_rather_than_refusing(self):
        assert "Protect your buffs from being taken 35% of the time" in self._said(
            "shepherds_crook"
        )

    def test_a_protecting_charge_counts_what_it_keeps(self):
        assert "• Protect 1 of your buffs from being taken" in self._said("king_crown")

    def test_protecting_the_other_players_debuffs_says_whose_they_are(self):
        assert (
            "Protect your opponent's debuffs from being taken 10% of the time "
            "for each malware [star]star[/star] item" in self._said("corrupted_kernel")
        )

    def test_a_share_of_maximum_health_says_it_is_a_share(self):
        said = self._said("sloth")
        assert "• Gain 10% maximum quota" in said
        assert "• Gain 15% maximum quota for each [star]star[/star] item" in said

    def test_shrinking_what_an_opponent_gains_names_the_source(self):
        assert (
            "Your opponent's maximum quota from items is reduced by 15%"
            in self._said("snowball")
        )


class TestWordsThatWereMissingOrWrong:
    """Lines that said the wrong thing, or nothing at all.

    An aura said "activation" for all four of the moments it can watch. A
    tag excluded from a zone lost its number. And setting off another item had
    no line whatever: every Potion carries a spillover clause and it has been
    describing as nothing since the day it was built.
    """

    def _said(self, item_id):
        return describe.lines(ITEM_CATALOG[item_id])

    def test_an_aura_says_which_moment_it_watches(self):
        # All four read as "activation" before, and a weapon that missed
        # activated without hitting.
        assert self._said("spike_launcher")[-1].startswith(
            "When a weapon [star]star[/star] item hits:"
        )

    def test_setting_off_another_item_is_no_longer_silent(self):
        assert (
            "• Set off every potion [star]star[/star] item, without using them up"
            in self._said("emergency_hotfix")
        ), "every Potion has carried this clause and said nothing about it"

    def test_a_chance_that_grows_is_said_the_way_the_source_game_says_it(self):
        assert self._said("blue_sage_collar") == [
            "When a weapon [star]star[/star] item hits: 7% chance for each "
            "[buff]compute[/buff] to gain 3 [buff]credits[/buff]"
        ]

    def test_an_excluded_tag_reads_as_a_prefix(self):
        # "a star item that are not sentinel" loses its number the moment the
        # noun is singular, which it is here.
        assert (
            "When a non-sentinel [star]star[/star] item activates: 10% chance "
            "to gain 1 [buff]regenerating[/buff]" in self._said("amulet_of_light")
        )

    def test_the_spikes_limits_fit_the_sentence_they_sit_in(self):
        said = self._said("thorn_elemental")
        assert (
            "Your [buff]spiked[/buff] return against Ranged blows is increased by 50%"
            in said
        )
        assert (
            "Your [buff]spiked[/buff] critical chance is increased by 10% for "
            "each feral [star]star[/star] item" in said
        )
class TestWhatAStatusIsWorth:
    """A chip beside a fighter reads "optimised x6" and the client has no way
    to say what six are worth. The rule is the server's, so the words are too.
    """

    def test_a_stack_says_what_it_does(self):
        optimised = describe.rule("optimized")

        assert optimised["shown"] == "optimised"
        assert optimised["kind"] == "buff"
        assert optimised["each"] == 2
        assert optimised["one"] == "Items trigger 2% faster"

    def test_several_stacks_are_the_same_sentence_with_the_total_in_it(self):
        """The client multiplies and drops the answer in. It does not know the
        rule that got there, and does not need to."""
        optimised = describe.rule("optimized")

        assert "{total}" in optimised["many"]
        assert optimised["many"].replace("{total}", str(optimised["each"] * 6)) == (
            "Items trigger 12% faster"
        )

    def test_a_debuff_says_it_is_one(self):
        assert describe.rule("memory_leaked")["kind"] == "debuff"
        assert describe.rule("throttled")["kind"] == "debuff"
        assert describe.rule("rate_limited")["kind"] == "debuff"

    def test_a_status_worth_no_number_is_only_described_one_way(self):
        """Credits are spent by the items that ask for them, and six of them
        do not do anything six times over."""
        credits = describe.rule("credits")

        assert credits["each"] == 0
        assert credits["many"] == ""
        assert credits["one"]

    def test_every_status_the_battle_can_apply_has_a_rule(self):
        """A status added to the engine without a line here would show up as a
        chip that explains nothing."""
        for rule in describe.every_rule():
            assert rule["shown"], rule["status"]
            assert rule["one"], f"{rule['status']} says nothing about itself"
            if rule["each"]:
                assert "{total}" in rule["many"], rule["status"]

    def test_the_rules_match_the_design_document(self):
        """Section 3.1 and 3.2 quote these numbers. They came from there, so
        they can drift."""
        worth = {rule["status"]: rule["each"] for rule in describe.every_rule()}

        assert worth["optimized"] == 2, "2% faster a stack"
        assert worth["throttled"] == 2, "2% slower a stack"
        assert worth["monitored"] == 1, "+1 damage a stack"
        assert worth["calibrated"] == 5, "+5% accuracy a stack"
        assert worth["rate_limited"] == 5, "-5% accuracy a stack"
        assert worth["regenerating"] == 1, "1 HP a stack every 2 seconds"
        assert worth["memory_leaked"] == 1, "1 damage a stack every 2 seconds"
        assert worth["spiked"] == 1, "1 damage a stack to a melee attacker"
        assert worth["draining"] == 1, "1 healed a stack on a melee hit"

    def test_the_names_are_the_ones_the_design_document_gives(self):
        """Section 3.1 and 3.2 name all ten. The identifiers are the source
        game's words, kept because the catalogue is written against them, so
        the two lists are not the same list and can drift -- Compute was shown
        as "calibrated" on every card until somebody read them side by side.
        """
        named = {rule["status"]: rule["shown"] for rule in describe.every_rule()}

        assert named["calibrated"] == "compute", "Section 3.1 calls it Compute"
        assert named["optimized"] == "optimised"
        assert named["monitored"] == "monitored"
        assert named["regenerating"] == "regenerating"
        assert named["spiked"] == "spiked"
        assert named["draining"] == "draining"
        assert named["credits"] == "credits"
        assert named["throttled"] == "throttled"
        assert named["memory_leaked"] == "memory leak"
        assert named["rate_limited"] == "rate limited"

    def test_no_name_a_player_reads_is_an_identifier(self):
        """A card reading "memory_leaked" is a card written for whoever wrote
        the catalogue."""
        for rule in describe.every_rule():
            assert "_" not in rule["shown"], rule["status"]

    def test_a_status_explains_itself_beyond_the_number(self):
        """A card that says only "Heals 1 every 2 seconds" leaves a player
        asking every two seconds of what."""
        spiked = describe.rule("spiked")

        assert spiked["detail"] == "Only when their blow lands.", (
            "the rule the number does not carry"
        )

    def test_nothing_says_more_than_it_has_to(self):
        """Written the way an item's own lines are written, and read on the
        same screen minutes apart. A detail is only for a rule the number does
        not carry, and most of them have none."""
        for rule in describe.every_rule():
            assert len(rule["one"]) <= 34, (
                f"{rule['status']}: {rule['one']!r} is a sentence where a "
                f"number would do"
            )
            assert len(rule["detail"]) <= 60, (
                f"{rule['status']}: {rule['detail']!r} is too much to read "
                f"in a battle"
            )

    def test_a_status_nobody_has_written_a_rule_for_still_answers(self):
        made_up = describe.rule("something_new")

        assert made_up["shown"] == "something new"
        assert made_up["one"] == "", "nothing to say rather than a crash"
