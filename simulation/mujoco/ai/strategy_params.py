"""Strategy parameters — exact match of headless.js S dict."""

DEFAULT_PARAMS = {
    'kp':               0.582,
    'searchPwm':        0.899,
    'trackPwm':         0.99,
    'chargePwm':        0.976,
    'chargeThreshold':  372,    # mm
    'evadeFrontTime':   0.45,   # seconds
    'evadeRearTime':    0.30,
    'evadeReverseRatio': 0.45,
    'evadePwm':         0.964,
    'edgeSteer':        0.453,
    'centerReturnTime': 0.35,
    'centerFill':       145,    # mm
    'searchDir':        1,      # 1=CW, -1=CCW
    'pwmScale':         1.0,
    'flankAngle':       0.51,   # radians
    'flankThreshold':   636,    # mm
    'flankPwm':         0.658,
    'flankEnabled':     1,
}


def merge_params(overrides: dict) -> dict:
    """Merge CLI overrides into default parameters."""
    params = DEFAULT_PARAMS.copy()
    for k, v in overrides.items():
        if k in params:
            params[k] = type(params[k])(v)
    return params
