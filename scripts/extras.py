"""v5 extras: intraday engine + backtest. Called after the ICT engine."""


def run_all():
    import backtest
    import intraday_engine
    for name, mod in (("intraday", intraday_engine), ("backtest", backtest)):
        try:
            mod.main()
        except Exception as e:
            print(f"{name} failed: {e}")
