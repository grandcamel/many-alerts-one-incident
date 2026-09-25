"""Local link consistency never establishes retrieved-response support."""

import pytest

from grafana_jsm_sandbox.report_links import (
    LinkPrecheck,
    ReportLinkError,
    precheck_claim_links,
)

CLAIM1 = "00000000-0000-4000-8000-000000000001"
CLAIM2 = "00000000-0000-4000-8000-000000000002"
CIT1 = "00000000-0000-4000-8000-000000000003"
CIT2 = "00000000-0000-4000-8000-000000000004"
EX1 = "00000000-0000-4000-8000-000000000005"


def _claim(**changes):
    claim = {
        "claim_id": CLAIM1,
        "observed_or_inferred": "observed",
        "status": "asserted",
        "evidence_refs": [CIT1],
        "derived_from": [],
    }
    claim.update(changes)
    return claim


def _citation(**changes):
    citation = {
        "citation_id": CIT1,
        "exchange_id": EX1,
        "provenance": "local_association",
        "source_interface": "fixture",
        "observation_status": "returned",
    }
    citation.update(changes)
    return citation


def _input(claims=None, citations=None):
    return {
        "claims": [_claim()] if claims is None else claims,
        "citations": [_citation()] if citations is None else citations,
    }


def _shape(call):
    with pytest.raises(ReportLinkError) as caught:
        call()
    assert caught.value.code == "report_link_shape"
    assert caught.value.args == ("report_link_shape",)


def test_consistent_links_and_empty_stubs_remain_support_unverified():
    result = precheck_claim_links(_input())
    assert result == LinkPrecheck(())
    assert result.support_status == "support_unverified"
    inferred = _claim(claim_id=CLAIM2, observed_or_inferred="inferred",
                      evidence_refs=[], derived_from=[CLAIM1])
    assert precheck_claim_links(_input(claims=[_claim(), inferred])).defects == ()
    assert precheck_claim_links(_input(claims=[], citations=[])) == LinkPrecheck(())


@pytest.mark.parametrize(("value", "defect"), [
    (_input(claims=[_claim(), _claim()]), "claim_duplicate"),
    (_input(citations=[_citation(), _citation()]), "citation_duplicate"),
    (_input(claims=[_claim(evidence_refs=[CIT2])]), "citation_dangling"),
    (_input(claims=[_claim(evidence_refs=[CIT1, CIT1])]), "reference_duplicate"),
    (_input(claims=[_claim(evidence_refs=[])]), "asserted_observed_unlinked"),
    (_input(claims=[_claim(derived_from=[CLAIM2])]), "observed_has_derivation"),
    (_input(claims=[_claim(claim_id=CLAIM2, observed_or_inferred="inferred",
                           evidence_refs=[], derived_from=[CLAIM1])]),
     "derivation_dangling"),
    (_input(claims=[_claim(claim_id=CLAIM2, observed_or_inferred="inferred",
                           evidence_refs=[], derived_from=[])]),
     "inference_without_observation"),
    (_input(claims=[
        _claim(observed_or_inferred="inferred", evidence_refs=[],
               derived_from=[CLAIM2]),
        _claim(claim_id=CLAIM2, observed_or_inferred="inferred",
               evidence_refs=[], derived_from=[CLAIM1]),
    ]), "derivation_not_observed"),
    (_input(citations=[_citation(provenance="native_returned")]),
     "native_provenance_mismatch"),
    (_input(citations=[_citation(exchange_id=None)]), "returned_without_exchange"),
])
def test_defects_are_fixed_codes_and_never_positive(value, defect):
    result = precheck_claim_links(value)
    assert defect in result.defects
    assert result.defects == tuple(sorted(set(result.defects)))
    assert result.support_status == "support_unverified"


def test_multiple_claims_may_share_one_citation():
    claims = [_claim(), _claim(claim_id=CLAIM2, status="unreviewed")]
    assert precheck_claim_links(_input(claims=claims)).defects == ()


def test_multiple_citations_may_refer_to_one_exchange():
    citations = [_citation(), _citation(citation_id=CIT2)]
    assert precheck_claim_links(_input(citations=citations)).defects == ()


@pytest.mark.parametrize("value", [
    {**_input(), "report_text": "private"},
    _input(claims=[{**_claim(), "text": "unsupported"}]),
    _input(citations=[{**_citation(), "query_or_reference": {"raw": "secret"}}]),
    _input(claims=[_claim(status="supported")]),
    _input(citations=[_citation(source_interface="invented")]),
    _input(citations=[_citation(observation_status="complete")]),
    _input(claims=[_claim(claim_id="UPPERCASE")]),
    _input(claims=[_claim(evidence_refs=[True])]),
    _input(claims=[_claim(evidence_refs=[CIT1] * 129)]),
    _input(claims=[[_claim()]]),
    _input(claims=[_claim()] * 65),
    _input(citations=[_citation()] * 129),
])
def test_malformed_or_oversized_stubs_fail_closed(value):
    _shape(lambda: precheck_claim_links(value))


def test_hostile_python_values_do_not_compare_or_format():
    class Hostile:
        __hash__ = object.__hash__

        def __eq__(self, other):
            raise AssertionError("hostile equality was reached")

        def __str__(self):
            raise AssertionError("hostile formatting was reached")

    for value in (
        _input(claims=[_claim(status=Hostile())]),
        _input(citations=[_citation(exchange_id=Hostile())]),
        {"claims": [], Hostile(): []},
    ):
        _shape(lambda value=value: precheck_claim_links(value))
