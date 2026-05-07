import random

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


def test_quick_pick_preserves_pick3_pair_shape():
    numbers = quick_pick("pick-3", "front-pair-50c", rng=random.Random(4))

    assert len(numbers) == 2
    assert all(0 <= number <= 9 for number in numbers)
