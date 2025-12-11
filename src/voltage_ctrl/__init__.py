"""
voltage-ctrl: Multi-Channel Power Supply Controller

A Python package for controlling voltage and current outputs via serial
communication with Arduino-based DAC systems.
"""

from .power_supply_controller import PowerSupplyController

__version__ = "0.1.0"
__author__ = "Your Name"
__all__ = ["PowerSupplyController"]

# Package-level constants
DAC_RESOLUTION = 4096  # 12-bit DAC
VOLTAGE_FULL_SCALE = 30.0  # Volts
CURRENT_SCALE_FACTOR = 200.0  # mA scaling
CURRENT_SAFETY_FACTOR = 1.1
