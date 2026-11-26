"""v5 extras: intraday engine + backtest. Called after the ICT engine."""


def run_all():
    import backtest
    import intraday_engine
    import robustness
    for name, mod in (("intraday", intraday_engine), ("backtest", backtest), ("robustness", robustness)):
        try:
            mod.main()
        except Exception as e:
            print(f"{name} failed: {e}")
