"""
Multi-Channel Power Supply Controller
Controls voltage and current outputs via serial communication
"""

import serial
import time
import numpy as np
from typing import List, Optional, Union


class VoltageController:
    """
    Controls voltage and current for multiple channels via serial communication.

    The controller communicates with an Arduino over a serial port to set
    voltages and currents using a 12-bit DAC.

    Can be used as a context manager for automatic resource cleanup:
        with VoltageController(com_port='COM3') as controller:
            controller.set_voltages([8, 9, 10], [5.0, 3.3, 2.5], v_max=10.0)
        # Serial connection automatically closed and channels zeroed
    """

    # DAC parameters
    DAC_RESOLUTION = 4096  # 12-bit DAC
    VOLTAGE_FULL_SCALE = 30.0  # Volts
    CURRENT_SCALE_FACTOR = 200.0  # mA scaling
    CURRENT_SAFETY_FACTOR = 1.1

    def __init__(
        self,
        com_port: str = "COM3",
        baud_rate: int = 9600,
        zero_on_exit: bool = True,
    ):
        """
        Initialise the power supply controller.

        Args:
            com_port: Serial port identifier (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baud_rate: Serial communication baud rate (default: 9600)
            zero_on_exit: If True, set all voltages to 0V when exiting context manager (default: True)
        """
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.zero_on_exit = zero_on_exit
        self.serial_conn: Optional[serial.Serial] = None
        self._context_active = False
        self._active_channels: List[int] = []  # Track channels that have been used

    def __enter__(self):
        """
        Enter the context manager.

        Returns:
            self: The VoltageController instance
        """
        self._context_active = True
        print(f"VoltageController context manager entered")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager and clean up resources.

        If zero_on_exit is True, sets all active channels to 0V before closing.
        Always ensures serial connection is closed.

        Args:
            exc_type: Exception type (if an exception occurred)
            exc_val: Exception value (if an exception occurred)
            exc_tb: Exception traceback (if an exception occurred)

        Returns:
            False: Don't suppress exceptions
        """
        try:
            if self.zero_on_exit and self._active_channels:
                print("\nZeroing all active channels before exit...")
                self._zero_channels(self._active_channels)
        except Exception as e:
            print(f"Warning: Error while zeroing channels: {e}")
        finally:
            # Always ensure serial connection is closed
            self._close_serial()
            self._context_active = False
            print("VoltageController context manager exited")

        # Don't suppress any exceptions that occurred in the with block
        return False

    def _zero_channels(self, channels: List[int]) -> None:
        """
        Set specified channels to 0V and minimal current limit.
        Used for safe shutdown.

        Args:
            channels: List of channel numbers to zero
        """
        try:
            self._open_serial()

            for channel in channels:
                # Set voltage to 0V
                self._send_command(channel, mode=0, value=0)
                # Set current limit to minimum
                self._send_command(channel, mode=1, value=0)

            print(f"Channels {channels} zeroed")

        except Exception as e:
            print(f"Error zeroing channels: {e}")
            raise
        finally:
            self._close_serial()

    def _open_serial(self) -> None:
        """Open serial connection and initialise Arduino."""
        # Only open if not already open
        if self.serial_conn and self.serial_conn.is_open:
            return

        print(f"\nOpening {self.com_port} at {self.baud_rate}")

        self.serial_conn = serial.Serial(
            port=self.com_port, baudrate=self.baud_rate, timeout=1
        )

        # Wait for Arduino to restart (it resets when serial connection opens)
        time.sleep(3)

        # Send initialisation data to clear Arduino's string buffer
        self.serial_conn.write(b"hello world")
        time.sleep(0.1)

    def _close_serial(self) -> None:
        """Close serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            print(f"Closing {self.com_port}")
            self.serial_conn.close()

    def _send_command(self, channel: int, mode: int, value: int) -> None:
        """
        Send a command to set voltage or current for a channel.

        Args:
            channel: Channel number
            mode: 0 for voltage, 1 for current
            value: DAC value (0-4095)
        """
        command = f"s{channel} {mode} {int(value)} e"
        self.serial_conn.write(command.encode())
        time.sleep(0.1)  # Wait between commands

    def _voltage_to_dac(self, voltage: float) -> int:
        """
        Convert voltage to DAC value.

        The scaling is: DAC_value = floor(voltage / 30V × 4096)

        Args:
            voltage: Desired voltage in volts

        Returns:
            DAC value (0-4095)
        """
        dac_value = voltage / self.VOLTAGE_FULL_SCALE * self.DAC_RESOLUTION
        return int(np.floor(dac_value))

    def _current_limit_to_dac(self, current_limit_ma: float) -> int:
        """
        Convert current limit to DAC value.

        Args:
            current_limit_ma: Current limit in milliamperes

        Returns:
            DAC value (0-4095)
        """
        dac_value = current_limit_ma / self.CURRENT_SCALE_FACTOR * self.DAC_RESOLUTION
        return int(np.floor(dac_value))

    def _update_active_channels(self, channels: List[int]) -> None:
        """
        Update the list of active channels.

        Args:
            channels: List of channel numbers being used
        """
        for ch in channels:
            if ch not in self._active_channels:
                self._active_channels.append(ch)

    def set_voltages(
        self,
        channels: List[int],
        voltages: List[float],
        v_max: float,
    ) -> None:
        """
        Set voltages only - no current limiting.

        WARNING: This function does not set current limits. Ensure your hardware
        has appropriate protection or you risk damaging components.

        Args:
            channels: List of channel numbers to control
            voltages: List of voltages (in volts) for each channel
            v_max: Maximum allowed voltage in volts

        Raises:
            ValueError: If channels and voltages lists have different lengths
        """
        if len(channels) != len(voltages):
            raise ValueError(
                f"Channels and voltages must have same length: "
                f"got {len(channels)} channels and {len(voltages)} voltages"
            )

        # Track these channels for potential zeroing on exit
        self._update_active_channels(channels)

        try:
            self._open_serial()

            print(f"Setting voltages for channels {channels}...")
            for channel, voltage in zip(channels, voltages):
                clamped_voltage = min(voltage, v_max)
                if voltage > v_max:
                    print(
                        f"Warning: voltage for channel {channel} ({voltage}V) "
                        f"exceeds v_max ({v_max}V), clamping"
                    )
                voltage_dac = self._voltage_to_dac(clamped_voltage)
                self._send_command(channel, mode=0, value=voltage_dac)

            self._close_serial()
            print("Voltages set!")

        except Exception as e:
            self._close_serial()
            raise

    def set_voltages_safe(
        self,
        channels: List[int],
        voltages: List[float],
        resistance: float,
        v_max: float,
    ) -> None:
        """
        Set voltages for specified channels with current limiting.

        This is the safe version that sets appropriate current limits based on
        the resistance and applied voltage.

        Args:
            channels: List of channel numbers to control
            voltages: List of voltages (in volts) for each channel
            resistance: Load resistance in ohms (used to calculate current limit)
            v_max: Maximum allowed voltage in volts

        Raises:
            ValueError: If channels and voltages lists have different lengths
        """
        if len(channels) != len(voltages):
            raise ValueError(
                f"Channels and voltages must have same length: "
                f"got {len(channels)} channels and {len(voltages)} voltages"
            )

        # Track these channels for potential zeroing on exit
        self._update_active_channels(channels)

        # Calculate maximum current limit
        i_max = v_max / resistance * self.CURRENT_SAFETY_FACTOR
        i_max_ma = i_max * 1000  # Convert to mA

        try:
            # First connection: Set initial current limits
            self._open_serial()

            print(f"Setting initial current limits for channels {channels}...")
            for channel in channels:
                current_dac = self._current_limit_to_dac(i_max_ma)
                self._send_command(channel, mode=1, value=current_dac)

            self._close_serial()

            # Second connection: Set voltages and final current limits
            self._open_serial()

            print(f"Setting voltages for channels {channels}...")
            for channel, voltage in zip(channels, voltages):
                voltage_dac = self._voltage_to_dac(voltage)

                # Check voltage limit
                if voltage > v_max:
                    print(
                        f"Warning: voltage of channel {channel} is too large, clamping to {v_max}V"
                    )
                    voltage = v_max
                    voltage_dac = self._voltage_to_dac(v_max)

                self._send_command(channel, mode=0, value=voltage_dac)

            print("Setting final current limits...")
            for channel, voltage in zip(channels, voltages):
                clamped_voltage = min(voltage, v_max)
                # Current limit based on actual voltage
                i_channel = clamped_voltage / resistance * self.CURRENT_SAFETY_FACTOR
                i_channel_ma = i_channel * 1000
                current_dac = self._current_limit_to_dac(i_channel_ma)
                self._send_command(channel, mode=1, value=current_dac)

            self._close_serial()

            print("Voltage setting complete!")

        except Exception as e:
            print(f"Error during voltage setting: {e}")
            self._close_serial()
            raise

    def get_dac_info(self) -> dict:
        """
        Get information about DAC configuration.

        Returns:
            Dictionary with DAC configuration details
        """
        return {
            "dac_resolution": self.DAC_RESOLUTION,
            "voltage_full_scale": self.VOLTAGE_FULL_SCALE,
            "voltage_per_bit": self.VOLTAGE_FULL_SCALE / self.DAC_RESOLUTION,
            "current_scale_factor": self.CURRENT_SCALE_FACTOR,
            "current_safety_factor": self.CURRENT_SAFETY_FACTOR,
        }


# Example usage
if __name__ == "__main__":
    # # Example 1: Using as a context manager (recommended)
    # print("\n=== Example 1: Context Manager Usage with Auto-Zeroing ===")
    # with VoltageController(com_port="COM3", baud_rate=9600) as controller:
    #     # Display DAC information
    #     info = controller.get_dac_info()
    #     print("\n=== Power Supply Configuration ===")
    #     print(f"DAC resolution: {info['dac_resolution']} bits")
    #     print(f"Voltage full scale: {info['voltage_full_scale']} V")
    #     print(f"Voltage per bit: {info['voltage_per_bit']:.4f} V")

    #     # Set voltages for specific channels
    #     channels = [8, 9, 10, 11, 12, 13, 14, 15]
    #     voltages = [5.0, 3.3, 2.5, 1.8, 4.2, 3.0, 2.8, 3.5]
    #     resistance = 50.0  # ohms
    #     v_max = 10.0  # volts

    #     controller.set_voltages_safe(channels, voltages, resistance, v_max)
    # # Voltages automatically zeroed and connection closed here

    # # Example 2: Setting different channels at different times
    # print("\n\n=== Example 2: Multiple Channel Sets ===")
    # with VoltageController(com_port="COM3", baud_rate=9600) as controller:
    #     # First set some channels
    #     channels_1 = [8, 9, 10]
    #     voltages_1 = [5.0, 3.3, 2.5]
    #     controller.set_voltages_safe(
    #         channels_1, voltages_1, resistance=50.0, v_max=10.0
    #     )

    #     # Later set different channels
    #     channels_2 = [11, 12, 13]
    #     voltages_2 = [1.8, 4.2, 3.0]
    #     controller.set_voltages_safe(
    #         channels_2, voltages_2, resistance=50.0, v_max=10.0
    #     )
    # # All channels (8-13) automatically zeroed on exit

    # # Example 3: Traditional usage (without context manager)
    # print("\n\n=== Example 3: Traditional Usage ===")
    # controller = VoltageController(com_port="COM3", baud_rate=9600)

    # channels = [8, 9, 10, 11]
    # voltages = [5.0, 3.3, 2.5, 1.8]
    # controller.set_voltages_safe(channels, voltages, resistance=50.0, v_max=10.0)
    # # Note: Voltages remain set, connection closed after set_voltages_safe() completes

    # # Example 4: Context manager without auto-zeroing
    # print("\n\n=== Example 4: Context Manager Without Auto-Zeroing ===")
    # with VoltageController(
    #     com_port="COM3", baud_rate=9600, zero_on_exit=False
    # ) as controller:
    #     channels = [8, 9, 10]
    #     voltages = [5.0, 3.3, 2.5]
    #     controller.set_voltages_safe(channels, voltages, resistance=50.0, v_max=10.0)
    # # Connection closed but voltages remain set

    # Example 5: Unsafe voltage setting (no current limits)
    print("\n\n=== Example 5: Unsafe Voltage Setting (No Current Limits) ===")
    controller = VoltageController(com_port="COM3", baud_rate=9600)
    channels = [8, 9]
    voltages = [3.3, 5.0]
    controller.set_voltages(channels, voltages, v_max=10.0)
    controller._close_serial()
    print("Warning: Current limits not set - ensure hardware protection is in place!")
