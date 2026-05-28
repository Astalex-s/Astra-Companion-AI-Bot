from bot.utils.formatters import split_message


class TestSplitMessage:
    def test_short_message_unchanged(self):
        assert split_message("Hello") == ["Hello"]

    def test_exact_limit_unchanged(self):
        text = "a" * 4096
        assert split_message(text) == [text]

    def test_splits_at_newline(self):
        text = "a" * 4000 + "\n" + "b" * 200
        chunks = split_message(text)
        assert len(chunks) == 2
        assert chunks[0] == "a" * 4000
        assert chunks[1] == "b" * 200

    def test_splits_at_space_if_no_newline(self):
        text = "word " * 1000  # 5000 chars
        chunks = split_message(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 4096

    def test_hard_split_no_space(self):
        text = "a" * 5000
        chunks = split_message(text)
        assert len(chunks) == 2
        assert chunks[0] == "a" * 4096
        assert chunks[1] == "a" * 904
