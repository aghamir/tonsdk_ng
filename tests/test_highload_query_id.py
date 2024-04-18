from tonsdk_ng.contract.wallet import HighloadQueryId


def test_highload_query_id_seqno():
    assert HighloadQueryId.from_seqno(0).to_seqno() == 0
    assert HighloadQueryId.from_seqno(1022).to_seqno() == 1022
    assert HighloadQueryId.from_seqno(1023).to_seqno() == 1023
    assert HighloadQueryId.from_seqno(1024).to_seqno() == 1024
    assert HighloadQueryId.from_seqno(8380415).to_seqno() == 8380415


def test_highload_query_id():
    MAX = (2**13) * 1023 - 2
    query_id = HighloadQueryId()
    for i in range(MAX):
        query_id = query_id.get_next()

        q = query_id.query_id
        q2 = HighloadQueryId.from_query_id(q)

        assert query_id.shift == q2.shift
        assert query_id.bit_number == q2.bit_number
        assert q2.query_id == q

        q3 = HighloadQueryId.from_shift_and_bit_number(
            query_id.shift, query_id.bit_number
        )
        assert query_id.shift == q3.shift
        assert query_id.bit_number == q3.bit_number
        assert q3.query_id == q

        if i == MAX - 1:
            assert not query_id.has_next()
        else:
            assert query_id.has_next()
