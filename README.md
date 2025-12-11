# Multi-Channel Voltage Controller

A Python class for controlling voltage and current outputs across multiple channels via serial communication with an Arduino-based DAC system.

## Overview

`VoltageController` provides a clean interface for setting voltages and current limits on multiple channels simultaneously. It communicates with an Arduino over a serial port using a 12-bit DAC to precisely control output parameters.

This controller was originally developed for controlling thermal phase shifters in photonic integrated circuits (specifically, a 4-tap FIR filter chip), but can be adapted for any multi-channel voltage supply application using similar hardware.

## Hardware Requirements

- Arduino with 12-bit DAC capability
- Serial connection (USB or RS-232)

## Installation

```bash
pip install pyserial numpy
```

## Quick Start

```python
from voltage_ctrl import VoltageController

# Define your channel numbers
channels = [8, 9, 10, 11, 12, 13, 14, 15]

# Create controller instance
controller = VoltageController(
    channels=channels,
    com_port='COM3',      # Use '/dev/ttyUSB0' on Linux
    baud_rate=9600
)

# Set voltages for all channels
voltages = [5.0, 3.3, 2.5, 1.8, 4.2, 3.0, 2.8, 3.5]  # Volts
resistance = 50.0  # Load resistance in ohms
v_max = 10.0       # Maximum voltage limit

controller.set_voltages(voltages, resistance, v_max)
```

## Class Reference

### `VoltageController(channels, com_port='COM3', baud_rate=9600)`

Initialises the power supply controller.

**Parameters:**
- `channels` (List[int]): List of channel numbers to control
- `com_port` (str): Serial port identifier (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
- `baud_rate` (int): Serial communication baud rate (default: 9600)

### Methods

#### `set_voltages(voltages, resistance, v_max)`

Sets voltages for all configured channels with automatic current limiting.

**Parameters:**
- `voltages` (List[float]): List of voltages in volts, must match number of channels
- `resistance` (float): Load resistance in ohms (used to calculate current limit)
- `v_max` (float): Maximum allowed voltage in volts

**Raises:**
- `ValueError`: If voltages list length doesn't match number of channels

**Behaviour:**
1. Opens serial connection and sets initial current limits based on maximum voltage
2. Closes and reopens connection (Arduino restarts)
3. Sets target voltages for each channel
4. Sets final current limits based on actual voltages
5. Closes connection

The two-stage process ensures current limits are properly configured before voltages are applied.

#### `get_channel_info()`

Returns configuration information about the controller.

**Returns:**
- `dict`: Dictionary containing:
  - `channels`: List of channel numbers
  - `num_channels`: Number of channels
  - `dac_resolution`: DAC resolution (4096 for 12-bit)
  - `voltage_full_scale`: Maximum voltage range (30 V)
  - `voltage_per_bit`: Voltage resolution per DAC bit

## DAC Conversion Formulas

The controller uses the following conversions:

**Voltage to DAC:**
$$\text{DAC}_{\text{voltage}} = \left\lfloor \frac{V_{\text{target}}}{30\,\text{V}} \times 4096 \right\rfloor$$

**Current Limit to DAC:**
$$\text{DAC}_{\text{current}} = \left\lfloor \frac{I_{\text{limit}}}{200\,\text{mA}} \times 4096 \right\rfloor$$

**Maximum Current Calculation:**
$$I_{\text{max}} = \frac{V_{\text{max}}}{R} \times 1.1$$

where the factor of 1.1 provides a 10% safety margin.

## Communication Protocol

Commands are sent as ASCII strings in the format:

```
s<channel> <mode> <value> e
```

Where:
- `<channel>`: Channel number
- `<mode>`: 0 for voltage, 1 for current limit
- `<value>`: DAC value (0-4095)
- `s` and `e`: Start and end delimiters

**Example:** `s8 0 683 e` sets channel 8 voltage to approximately 5.0 V

## Important Notes

### Serial Connection Timing

- The Arduino resets when the serial connection opens (3-second delay required)
- 100 ms delay between commands prevents buffer overflow
- Initialisation string ("hello world") clears the Arduino's buffer

### Voltage and Current Limits

- Maximum voltage: 30 V (hardware limit)
- DAC resolution: 12-bit (4096 levels)
- Voltage resolution: ~7.3 mV per bit
- Current limits are automatically calculated based on load resistance
- 10% safety factor applied to current limits

### Error Handling

- Voltages exceeding `v_max` are automatically clamped
- Warning messages printed for clamped voltages
- Serial connection closed on exceptions

## Example Use Cases

### Setting Uniform Voltage

```python
channels = [8, 9, 10, 11, 12, 13, 14, 15]
controller = VoltageController(channels)

# Set all channels to 3.3V
voltages = [3.3] * len(channels)
controller.set_voltages(voltages, resistance=50.0, v_max=10.0)
```

### Viewing Configuration

```python
info = controller.get_channel_info()
print(f"Controlling {info['num_channels']} channels")
print(f"Voltage resolution: {info['voltage_per_bit']:.4f} V/bit")
```

### Ramping Voltages

```python
import numpy as np

channels = [8, 9, 10, 11]
controller = VoltageController(channels)

# Create voltage gradient
voltages = np.linspace(1.0, 5.0, len(channels))
controller.set_voltages(voltages.tolist(), resistance=100.0, v_max=6.0)
```

## Platform Compatibility

### Windows
```python
controller = VoltageController(channels, com_port='COM3')
```

### Linux/macOS
```python
controller = VoltageController(channels, com_port='/dev/ttyUSB0')
```

To find your serial port:
- **Windows:** Check Device Manager → Ports (COM & LPT)
- **Linux:** Run `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
- **macOS:** Run `ls /dev/tty.*`

## Troubleshooting

### Serial Port Not Found
- Check that the Arduino is connected
- Verify the port name matches your system
- Ensure you have permissions to access the serial port (Linux: add user to `dialout` group)

### Arduino Not Responding
- Increase the post-connection delay (currently 3 seconds)
- Check baud rate matches Arduino configuration
- Verify Arduino sketch is running correctly

### Voltage Not Setting Correctly
- Check DAC calibration
- Verify load resistance value is correct
- Ensure voltage doesn't exceed hardware limits

## Migrating from MATLAB

This Python implementation is equivalent to the MATLAB function `power_supply_write_4tap.m`. Key differences:

- Object-oriented design vs. function-based
- Uses pySerial instead of MATLAB's serial objects
- Type hints and comprehensive error handling
- Channel configuration passed at initialisation

## Licence

This code is provided as-is for research and educational purposes.

## Contributing

When modifying this code:
1. Maintain the two-stage voltage/current setting process
2. Preserve timing delays (critical for Arduino communication)
3. Keep safety factors for current limits
4. Update documentation for any protocol changes
