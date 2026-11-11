"""Reference-interval linear standardization used for CWC EHR laboratory values.

x is the original measurement; z is the released dimensionless score. L and U
are the applicable lower and upper reference limits, with U > L. The measurement
and both limits use the same original unit. Select the
analyte-specific and, where applicable, sex-specific limits before conversion.
The executable example uses illustrative values, not patient data or clinical
reference limits.
"""


def standardize(x, lower, upper):
    """Return z = (x - L) / (U - L) for the applicable reference interval."""
    if upper <= lower:
        raise ValueError("The upper reference limit must exceed the lower limit.")
    return (x - lower) / (upper - lower)


def original_scale(z, lower, upper):
    """Return x = L + z * (U - L) for the same reference interval."""
    if upper <= lower:
        raise ValueError("The upper reference limit must exceed the lower limit.")
    return lower + z * (upper - lower)


if __name__ == "__main__":
    lower, upper = 10, 20
    print("Illustrative values only; L = 10, U = 20")
    print("x,z,original_scale_x")
    for x in (5, 10, 15, 20, 25):
        z = standardize(x, lower, upper)
        print(f"{x:g},{z:g},{original_scale(z, lower, upper):g}")
