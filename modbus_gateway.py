# modbus_gateway.py

import socket
import serial  # from pyserial

class ModbusGateway:
    def __init__(self, cfg):
        self.type = cfg['connection_type']
        if self.type == 'ethernet':
            self.host = cfg['rs485gate_ip']
            self.port = cfg['rs485gate_port']
            self.timeout = cfg.get('connection_timeout', 3)
            self._sock = None
        elif self.type == 'serial':
            self.port_name = cfg['serial_port']
            self.baudrate = cfg.get('serial_baudrate', 115200)
            self.timeout = cfg.get('serial_timeout', 3)
            self._serial = None
        else:
            raise ValueError(f"Unknown connection type: {self.type}")

    def open(self):
        if self.type == 'ethernet':
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
        else:
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=self.timeout
            )

    def close(self):
        if self.type == 'ethernet' and self._sock:
            self._sock.close()
        elif self.type == 'serial' and self._serial:
            self._serial.close()

    def send(self, data: bytes):
        if self.type == 'ethernet':
            self._sock.send(data)
        else:
            # Some serial gateways need a CRC or a header; adjust as needed
            self._serial.write(data)

    def recv(self, size: int) -> bytes:
        if self.type == 'ethernet':
            return self._sock.recv(size)
        else:
            return self._serial.read(size)
