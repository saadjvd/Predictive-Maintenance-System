from typing import Optional, Dict, Tuple, Callable


class UnitConversionError(Exception):
    """Base exception for unit normalization errors."""
    pass


class IncompatibleUnitError(UnitConversionError):
    """Raised when attempting to convert between incompatible physical dimensions."""
    pass


class UnsupportedUnitError(UnitConversionError):
    """Raised when an engineering unit is not supported."""
    pass


class UnitNormalizer:
    """Universal physical dimension unit normalization engine.
    
    Adheres strictly to Phase 4, Step 6 requirements:
    - Explicit supported unit conversions only
    - Strictly rejects conversions across incompatible physical dimensions
    - Never assumes vibration acceleration (g) and velocity (mm/s) are interchangeable
    - Preserves high numeric precision
    """

    # Supported units classified by physical dimension
    DIMENSION_UNITS: Dict[str, list[str]] = {
        "temperature": ["°c", "c", "celsius", "°f", "f", "fahrenheit", "k", "kelvin"],
        "velocity": ["mm/s", "mm/sec", "m/s", "in/s", "ips"],
        "acceleration": ["g", "m/s²", "m/s2", "mg"],
        "pressure": ["bar", "kpa", "psi", "mbar", "pa", "mpa"],
        "electric_current": ["a", "amp", "amps", "ma", "milliamp"],
        "rotational_speed": ["rpm", "cpm", "hz", "rad/s"],
        "count": ["count", "cycles", "units", "pcs", "batches"],
        "discrete": ["boolean", "binary", "state", "flag", "status"],
    }

    # Canonical base units for each physical dimension
    CANONICAL_UNITS: Dict[str, str] = {
        "temperature": "°C",
        "velocity": "mm/s",
        "acceleration": "g",
        "pressure": "bar",
        "electric_current": "A",
        "rotational_speed": "RPM",
        "count": "Count",
        "discrete": "Boolean",
    }

    @classmethod
    def clean_unit(cls, unit: Optional[str]) -> str:
        """Standardize unit string representation."""
        if not unit:
            return ""
        return unit.strip().lower()

    @classmethod
    def get_dimension(cls, unit: Optional[str]) -> Optional[str]:
        """Identify the physical dimension of an engineering unit."""
        if not unit:
            return None
        cleaned = cls.clean_unit(unit)
        for dim, units in cls.DIMENSION_UNITS.items():
            if cleaned in units:
                return dim
        return None

    @classmethod
    def are_compatible(cls, unit_a: Optional[str], unit_b: Optional[str]) -> bool:
        """Check whether two units share the same physical measurement dimension."""
        if not unit_a or not unit_b:
            return False
        dim_a = cls.get_dimension(unit_a)
        dim_b = cls.get_dimension(unit_b)
        return dim_a is not None and dim_a == dim_b

    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert a scalar value from source unit to target unit.
        
        Raises IncompatibleUnitError if units belong to different dimensions.
        Raises UnsupportedUnitError if either unit is unknown.
        """
        if value is None:
            return None

        u_from = cls.clean_unit(from_unit)
        u_to = cls.clean_unit(to_unit)

        if u_from == u_to:
            return float(value)

        dim_from = cls.get_dimension(from_unit)
        dim_to = cls.get_dimension(to_unit)

        if not dim_from:
            raise UnsupportedUnitError(f"Unsupported source engineering unit: '{from_unit}'")
        if not dim_to:
            raise UnsupportedUnitError(f"Unsupported target engineering unit: '{to_unit}'")

        if dim_from != dim_to:
            raise IncompatibleUnitError(
                f"Cannot convert incompatible physical dimensions: "
                f"'{from_unit}' ({dim_from}) to '{to_unit}' ({dim_to})."
            )

        # 1. TEMPERATURE (°C base)
        if dim_from == "temperature":
            # To Celsius
            if u_from in ("°c", "c", "celsius"):
                celsius = value
            elif u_from in ("°f", "f", "fahrenheit"):
                celsius = (value - 32.0) * (5.0 / 9.0)
            elif u_from in ("k", "kelvin"):
                celsius = value - 273.15
            else:
                raise UnsupportedUnitError(f"Unknown temperature unit: {from_unit}")

            # From Celsius to target
            if u_to in ("°c", "c", "celsius"):
                return celsius
            elif u_to in ("°f", "f", "fahrenheit"):
                return (celsius * (9.0 / 5.0)) + 32.0
            elif u_to in ("k", "kelvin"):
                return celsius + 273.15

        # 2. VIBRATION VELOCITY (mm/s base)
        elif dim_from == "velocity":
            # To mm/s
            if u_from in ("mm/s", "mm/sec"):
                base = value
            elif u_from in ("in/s", "ips"):
                base = value * 25.4
            elif u_from in ("m/s",):
                base = value * 1000.0
            else:
                raise UnsupportedUnitError(f"Unknown velocity unit: {from_unit}")

            # From mm/s to target
            if u_to in ("mm/s", "mm/sec"):
                return base
            elif u_to in ("in/s", "ips"):
                return base / 25.4
            elif u_to in ("m/s",):
                return base / 1000.0

        # 3. VIBRATION ACCELERATION (g base)
        elif dim_from == "acceleration":
            # To g
            if u_from in ("g",):
                base = value
            elif u_from in ("m/s²", "m/s2"):
                base = value / 9.80665
            elif u_from in ("mg",):
                base = value / 1000.0
            else:
                raise UnsupportedUnitError(f"Unknown acceleration unit: {from_unit}")

            # From g to target
            if u_to in ("g",):
                return base
            elif u_to in ("m/s²", "m/s2"):
                return base * 9.80665
            elif u_to in ("mg",):
                return base * 1000.0

        # 4. PRESSURE (bar base)
        elif dim_from == "pressure":
            # To bar
            if u_from == "bar":
                base = value
            elif u_from == "kpa":
                base = value / 100.0
            elif u_from == "psi":
                base = value * 0.0689475729
            elif u_from == "mbar":
                base = value / 1000.0
            elif u_from == "pa":
                base = value / 100000.0
            elif u_from == "mpa":
                base = value * 10.0
            else:
                raise UnsupportedUnitError(f"Unknown pressure unit: {from_unit}")

            # From bar to target
            if u_to == "bar":
                return base
            elif u_to == "kpa":
                return base * 100.0
            elif u_to == "psi":
                return base / 0.0689475729
            elif u_to == "mbar":
                return base * 1000.0
            elif u_to == "pa":
                return base * 100000.0
            elif u_to == "mpa":
                return base / 10.0

        # 5. ELECTRIC CURRENT (A base)
        elif dim_from == "electric_current":
            if u_from in ("a", "amp", "amps"):
                base = value
            elif u_from in ("ma", "milliamp"):
                base = value / 1000.0
            else:
                raise UnsupportedUnitError(f"Unknown current unit: {from_unit}")

            if u_to in ("a", "amp", "amps"):
                return base
            elif u_to in ("ma", "milliamp"):
                return base * 1000.0

        # 6. ROTATIONAL SPEED (RPM base)
        elif dim_from == "rotational_speed":
            if u_from in ("rpm", "cpm"):
                base = value
            elif u_from == "hz":
                base = value * 60.0
            elif u_from == "rad/s":
                import math
                base = value * 60.0 / (2.0 * math.pi)
            else:
                raise UnsupportedUnitError(f"Unknown rotational speed unit: {from_unit}")

            if u_to in ("rpm", "cpm"):
                return base
            elif u_to == "hz":
                return base / 60.0
            elif u_to == "rad/s":
                import math
                return base * (2.0 * math.pi) / 60.0

        # 7. COUNT / DISCRETE
        elif dim_from in ("count", "discrete"):
            return float(value)

        raise UnsupportedUnitError(f"Unsupported conversion dimension: {dim_from}")

