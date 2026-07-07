try:
    from yanantin.llika import Facet, FacetDiscrimination, best_for_recall
except (AttributeError, ImportError):
    from yanantin.llika.facets import Facet, FacetDiscrimination, best_for_recall


def facet(name: str, distinct: int, entropy: float, discriminating: bool) -> Facet:
    return Facet(
        name=name,
        distinct=distinct,
        entropy=entropy,
        discriminating=discriminating,
        top=((f"{name}-example", 1),),
    )


def disc(*facets: Facet, result_size: int = 1_000) -> FacetDiscrimination:
    return FacetDiscrimination(result_size=result_size, facets=facets)


def test_best_for_recall_prefers_high_cardinality_over_boolean_split() -> None:
    boolean_split = facet("has_attachment", distinct=2, entropy=0.95, discriminating=True)
    session = facet("session_id", distinct=101, entropy=0.89, discriminating=True)

    assert best_for_recall(disc(boolean_split, session)) is session


def test_best_for_recall_returns_none_when_nothing_discriminates() -> None:
    singleton = facet("workspace", distinct=1, entropy=0.0, discriminating=False)
    empty_signal = facet("kind", distinct=2, entropy=0.0, discriminating=False)

    assert best_for_recall(disc(singleton, empty_signal)) is None


def test_best_for_recall_ignores_non_discriminating_facets() -> None:
    weak_but_wide = facet("raw_marker", distinct=1_000, entropy=0.05, discriminating=False)
    useful_boolean = facet("is_decision", distinct=2, entropy=0.92, discriminating=True)

    assert best_for_recall(disc(weak_but_wide, useful_boolean)) is useful_boolean


def test_best_for_recall_returns_the_only_discriminating_facet() -> None:
    singleton = facet("project", distinct=1, entropy=0.0, discriminating=False)
    only_candidate = facet("author", distinct=12, entropy=0.74, discriminating=True)

    assert best_for_recall(disc(singleton, only_candidate)) is only_candidate


def test_best_for_recall_near_tie_prefers_higher_raw_information_content() -> None:
    higher_entropy = facet("topic", distinct=32, entropy=0.96, discriminating=True)
    higher_recall_value = facet("thread", distinct=64, entropy=0.81, discriminating=True)

    assert best_for_recall(disc(higher_entropy, higher_recall_value)) is higher_recall_value
