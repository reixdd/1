from jarvis.models import MarketIdentity, Observation


def test_evm_identity_lowercases_contract_and_pool():
    ident = MarketIdentity(chain="BASE", contract="0xAbC", pool="0xDeF")
    assert ident.chain == "base"
    assert ident.contract == "0xabc"
    assert ident.pool == "0xdef"
    assert ident.key == "base:0xabc:0xdef"


def test_solana_identity_preserves_case():
    ident = MarketIdentity(chain="sol", contract="AbCdEf", pool="PoOl")
    assert ident.contract == "AbCdEf"
    assert ident.pool == "PoOl"


def test_observation_exposes_identity(young_observation):
    assert young_observation.identity.key == "base:0xabcdef:0xpool123"
