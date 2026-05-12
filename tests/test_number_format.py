import random

import pytest

from nolottery.number_format import quick_pick


def test_quick_pick_uses_powerball_number_format():
    numbers = quick_pick("powerball", "standard", rng=random.Random(4))

    assert len(numbers) == 6
    assert numbers[:5] == tuple(sorted(numbers[:5]))
    assert len(set(numbers[:5])) == 5
    assert all(1 <= number <= 69 for number in numbers[:5])
    assert 1 <= numbers[5] <= 26


def test_quick_pick_uses_option_count_for_daily_keno():
    numbers = quick_pick("daily-keno", "4-spot", rng=random.Random(4))

    assert len(numbers) == 4
    assert numbers == tuple(sorted(numbers))
    assert len(set(numbers)) == 4
    assert all(1 <= number <= 80 for number in numbers)


def test_quick_pick_uses_option_count_for_michigan_club_keno():
    numbers = quick_pick("michigan-club-keno", "4-spot", rng=random.Random(4))

    assert len(numbers) == 4
    assert numbers == tuple(sorted(numbers))
    assert len(set(numbers)) == 4
    assert all(1 <= number <= 80 for number in numbers)


def test_quick_pick_uses_fixed_count_for_new_york_keno_style_games():
    quick_draw = quick_pick("quick-draw", "10-spot", rng=random.Random(4))
    pick_10 = quick_pick("pick-10", "standard", rng=random.Random(4))

    assert len(quick_draw) == 20
    assert quick_draw == tuple(sorted(quick_draw))
    assert len(set(quick_draw)) == 20
    assert all(1 <= number <= 80 for number in quick_draw)
    assert len(pick_10) == 10
    assert pick_10 == tuple(sorted(pick_10))
    assert len(set(pick_10)) == 10
    assert all(1 <= number <= 80 for number in pick_10)


def test_quick_pick_preserves_pick3_pair_shape():
    numbers = quick_pick("pick-3", "front-pair-50c", rng=random.Random(4))

    assert len(numbers) == 2
    assert all(0 <= number <= 9 for number in numbers)


@pytest.mark.parametrize(
    ("game_slug", "expected_length"),
    [
        ("dc-3", 3),
        ("dc-4", 4),
        ("dc-5", 5),
        ("georgia-cash-3", 3),
        ("georgia-cash-4", 4),
        ("georgia-five", 5),
        ("minnesota-pick-3", 3),
        ("michigan-daily-3", 3),
        ("michigan-daily-4", 4),
        ("mississippi-cash-3", 3),
        ("mississippi-cash-4", 4),
    ],
)
def test_quick_pick_supports_fixed_prize_digit_games(game_slug, expected_length):
    numbers = quick_pick(game_slug, "straight-1", rng=random.Random(4))

    assert len(numbers) == expected_length
    assert all(0 <= number <= 9 for number in numbers)


@pytest.mark.parametrize(
    ("game_slug", "option_slug", "expected_length", "minimum", "maximum"),
    [
        ("michigan-cash-pop", "one-pop", 1, 1, 15),
        ("michigan-fantasy-5", "standard", 5, 1, 39),
        ("michigan-keno", "standard", 10, 1, 80),
        ("michigan-lotto-47", "standard", 6, 1, 47),
        ("michigan-poker-lotto", "standard", 5, 1, 52),
    ],
)
def test_quick_pick_supports_michigan_local_number_games(
    game_slug,
    option_slug,
    expected_length,
    minimum,
    maximum,
):
    numbers = quick_pick(game_slug, option_slug, rng=random.Random(4))

    assert len(numbers) == expected_length
    assert numbers == tuple(sorted(numbers))
    assert len(set(numbers)) == expected_length
    assert all(minimum <= number <= maximum for number in numbers)
