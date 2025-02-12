import aws_lambda


def test_help(capsys):
    return_code = aws_lambda.main("help")
    assert not return_code
    captured = capsys.readouterr()
    assert "Available commands:" in captured.out
    assert not captured.err


def test_unknown_command(capsys):
    return_code = aws_lambda.main("neverheardof")
    assert return_code
    captured = capsys.readouterr()
    assert "Available commands:" in captured.out
    assert "neverheardof" in captured.err
