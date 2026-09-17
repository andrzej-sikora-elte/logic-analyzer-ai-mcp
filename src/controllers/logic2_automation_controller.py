import os
from typing import List, Optional, Dict
from saleae.automation import Manager, LogicDeviceConfiguration, CaptureConfiguration, TimedCaptureMode, DeviceType

class Logic2AutomationController:
    """Controller for managing Logic 2 automation device configurations and captures."""
    
    def __init__(self, manager: Manager):
        """
        Initialize the Logic 2 automation controller.
        
        Args:
            manager (Manager): Logic 2 automation manager instance
        """
        self.manager = manager
        self._device_configs: Dict[str, LogicDeviceConfiguration] = {}
        self._capture_configs: Dict[str, CaptureConfiguration] = {}
        
    def create_device_config(self, 
                           name: str,
                           digital_channels: List[int],
                           digital_sample_rate: int,
                           analog_channels: Optional[List[int]] = None,
                           analog_sample_rate: Optional[int] = None,
                           digital_threshold_volts: Optional[float] = None) -> str:
        """
        Create a new device configuration.
        
        Args:
            name (str): Name for the configuration
            digital_channels (List[int]): List of digital channels to enable
            digital_sample_rate (int): Digital sample rate in Hz
            analog_channels (List[int], optional): List of analog channels to enable
            analog_sample_rate (int, optional): Analog sample rate in Hz
            digital_threshold_volts (float, optional): Digital threshold voltage
            
        Returns:
            str: Configuration name
        """
        config = LogicDeviceConfiguration(
            enabled_digital_channels=digital_channels,
            digital_sample_rate=digital_sample_rate,
            enabled_analog_channels=analog_channels or [],
            analog_sample_rate=analog_sample_rate,
            digital_threshold_volts=digital_threshold_volts
        )
        self._device_configs[name] = config
        return name
        
    def create_capture_config(self,
                            name: str,
                            duration_seconds: float,
                            buffer_size_megabytes: Optional[int] = None) -> str:
        """
        Create a new capture configuration.
        
        Args:
            name (str): Name for the configuration
            duration_seconds (float): Capture duration in seconds
            buffer_size_megabytes (int, optional): Buffer size in MB
            
        Returns:
            str: Configuration name
        """
        config = CaptureConfiguration(
            capture_mode=TimedCaptureMode(duration_seconds=duration_seconds),
            buffer_size_megabytes=buffer_size_megabytes
        )
        self._capture_configs[name] = config
        return name
        
    def get_device_config(self, name: str) -> Optional[LogicDeviceConfiguration]:
        """Get a device configuration by name."""
        return self._device_configs.get(name)
        
    def get_capture_config(self, name: str) -> Optional[CaptureConfiguration]:
        """Get a capture configuration by name."""
        return self._capture_configs.get(name)
        
    def list_device_configs(self) -> List[str]:
        """List all available device configurations."""
        return list(self._device_configs.keys())
        
    def list_capture_configs(self) -> List[str]:
        """List all available capture configurations."""
        return list(self._capture_configs.keys())
        
    def remove_device_config(self, name: str) -> bool:
        """Remove a device configuration."""
        if name in self._device_configs:
            del self._device_configs[name]
            return True
        return False
        
    def remove_capture_config(self, name: str) -> bool:
        """Remove a capture configuration."""
        if name in self._capture_configs:
            del self._capture_configs[name]
            return True
        return False
        
    def get_available_devices(self) -> List[Dict]:
        """
        Get list of available Logic devices.
        
        Returns:
            List[Dict]: List of device information dictionaries with masked device IDs
        """
        if self.manager is None:
            raise RuntimeError(
                "Not connected to the Saleae Logic 2 Automation API. "
                "Make sure Logic 2 is running with 'Enable Automation Server' turned on "
                "(Logic 2 window, bottom-left Automation panel), then restart this MCP server."
            )
        devices = self.manager.get_devices()
        return [
            {
                'id': f"{device.device_id[:4]}...{device.device_id[-4:]}" if len(device.device_id) > 8 else "****",
                'type': device.device_type,
                'is_simulation': device.is_simulation
            }
            for device in devices
        ]
        
    def find_device_by_type(self, device_type: DeviceType) -> Optional[Dict]:
        """
        Find a device by its type.
        
        Args:
            device_type (DeviceType): Type of device to find
            
        Returns:
            Optional[Dict]: Device information if found, None otherwise
            
        Raises:
            ValueError: If the device type is not supported
        """
        devices = self.get_available_devices()
        for device in devices:
            if device['type'] == device_type:
                return device
        return None

    def run_capture(self,
                     output_dir: str,
                     duration_seconds: float = 2.0,
                     digital_channels: Optional[List[int]] = None,
                     digital_sample_rate: Optional[int] = None,
                     analog_channels: Optional[List[int]] = None,
                     analog_sample_rate: Optional[int] = None,
                     digital_threshold_volts: Optional[float] = None,
                     device_id: Optional[str] = None,
                     capture_name: str = "capture",
                     max_preview_lines: int = 200) -> Dict:
        """
        Trigger a real, timed capture on a connected Saleae Logic device using the
        Automation API, save it as a native .sal file, export raw digital/analog
        data to CSV in output_dir, and return a preview of the exported data so the
        result is usable without a separate file read.
        """
        if self.manager is None:
            raise RuntimeError(
                "Not connected to the Saleae Logic 2 Automation API. "
                "Make sure Logic 2 is running with 'Enable Automation Server' turned on "
                "(Logic 2 window, bottom-left Automation panel), then restart this MCP server."
            )

        if device_id is None:
            devices = self.manager.get_devices()
            if not devices:
                raise RuntimeError("No Saleae Logic devices found.")
            device_id = devices[0].device_id

        if digital_channels is None and analog_channels is None:
            digital_channels = [0, 1, 2, 3, 4, 5, 6, 7]

        # Logic 2 requires an explicit, device-supported sample rate; 8 MHz is a
        # safe default supported across Logic 8-class devices with 8 digital channels.
        if digital_channels and digital_sample_rate is None:
            digital_sample_rate = 8_000_000

        device_kwargs = {
            "enabled_digital_channels": digital_channels or [],
            "enabled_analog_channels": analog_channels or [],
        }
        if digital_sample_rate is not None:
            device_kwargs["digital_sample_rate"] = digital_sample_rate
        if analog_sample_rate is not None:
            device_kwargs["analog_sample_rate"] = analog_sample_rate
        if digital_threshold_volts is not None:
            device_kwargs["digital_threshold_volts"] = digital_threshold_volts

        device_config = LogicDeviceConfiguration(**device_kwargs)
        capture_config = CaptureConfiguration(
            capture_mode=TimedCaptureMode(duration_seconds=duration_seconds)
        )

        os.makedirs(output_dir, exist_ok=True)
        sal_path = os.path.join(output_dir, f"{capture_name}.sal")

        with self.manager.start_capture(
            device_id=device_id,
            device_configuration=device_config,
            capture_configuration=capture_config,
        ) as capture:
            capture.wait()
            capture.save_capture(sal_path)
            capture.export_raw_data_csv(
                directory=output_dir,
                digital_channels=digital_channels or None,
                analog_channels=analog_channels or None,
            )

        result: Dict = {
            "device_id": device_id,
            "sal_file": sal_path,
            "output_dir": output_dir,
            "duration_seconds": duration_seconds,
        }

        csv_files = sorted(f for f in os.listdir(output_dir) if f.endswith(".csv"))
        previews = {}
        for fname in csv_files:
            fpath = os.path.join(output_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                previews[fname] = {
                    "path": fpath,
                    "total_lines": len(lines),
                    "truncated": len(lines) > max_preview_lines,
                    "preview": "".join(lines[:max_preview_lines]),
                }
            except Exception as e:
                previews[fname] = {"path": fpath, "error": str(e)}
        result["csv_files"] = previews
        return result
