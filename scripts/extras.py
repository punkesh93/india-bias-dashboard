"""v5 extras: intraday engine + backtest. Called after the ICT engine."""


def run_all():
    import backtest
    import intraday_engine
    import robustness
    import positioning_study
    for name, mod in (("intraday", intraday_engine), ("backtest", backtest), ("robustness", robustness), ("positioning", positioning_study)):
        try:
            mod.main()
        except Exception as e:
            print(f"{name} failed: {e}")
