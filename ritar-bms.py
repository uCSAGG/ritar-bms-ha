#!/usr/bin/env python3

import time
import binascii
import socket
import os
import sys
import yaml
import json
import xml.etree.ElementTree as ET
import paho.mqtt.client as mqtt
import warnings

from protocol import *  # Import all queries from protocol.py

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Static variables for checking voltages and cells
cell_min_limit = 2450
cell_max_limit = 4750
volt_min_limit = 40.00
volt_max_limit = 60.00
temp_min_limit = -50
temp_max_limit = 70

# Let's assume we have a global dictionary to store the last valid cycle count value
last_valid_cycle_count = {}

# Function to load configuration from JSON or YAML
def load_config():
    config = {}

    # Check for options.json
    if os.path.exists('/data/options.json'):
        print("Loading options.json")
        with open('/data/options.json', 'r') as file:
            config = json.load(file)
#            print("Config loaded from options.json: " + json.dumps(config))

    # Check for config.yaml
    elif os.path.exists('config.yaml'):
        print("Loading config.yaml")
        with open('config.yaml', 'r') as file:
            yaml_config = yaml.load(file, Loader=yaml.FullLoader)
            # Assuming 'options' is a section in the YAML file
            config = yaml_config.get('options', {})
            print("Config loaded from config.yaml: " + json.dumps(config))

    # No configuration file found
    else:
        sys.exit("Error: No config file found (options.json or config.yaml)")

    return config

# Function to process and validate delay values
def validate_queries_delay(queries_delay, next_battery_delay):
    def convert_to_float(value, name):
        if isinstance(value, str):
            value = value.replace(",", ".")
        try:
            return float(value)
        except ValueError:
            print(f"Error: '{name}' must be a valid number. Found: {value}")
            sys.exit(1)

    queries_delay = convert_to_float(queries_delay, "queries_delay")
    next_battery_delay = convert_to_float(next_battery_delay, "next_battery_delay")

    return queries_delay, next_battery_delay

# Load the configuration
config = load_config()

# Ritar Battery Model
battery_model = config.get('battery_model', 'BAT-5KWH-51.2V')

# Get values from the configuration, with defaults where necessary
read_timeout = config.get('read_timeout', 30)  # Default to 30 seconds if not specified
connection_timeout = config.get('connection_timeout', 3)  # Default to 3 seconds if not specified

# Fetch values from config with defaults
queries_delay = config.get('queries_delay', '0.1')  # Default to '0.1' if not specified
next_battery_delay = config.get('next_battery_delay', '0.5')  # Default to '0.5' if not specified

# MQTT connection parameters (load from config if needed)
mqtt_broker = config.get("mqtt_broker", "core-mosquitto")
mqtt_port = config.get("mqtt_port", 1883)
mqtt_username = config.get("mqtt_username", "homeassistant")
mqtt_password = config.get("mqtt_password", "mqtt_password_here")

# Validate and convert all to valid format
queries_delay, next_battery_delay = validate_queries_delay(
    queries_delay, next_battery_delay
)

# Print the config values for confirmation
print(f"...")
print(f"RS485 to Ethernet Gate...")
print(f"IP Address: {config['rs485gate_ip']}")
print(f"Port: {config['rs485gate_port']} ")
print(f"...")
print(f"Connection Timeout: {connection_timeout} seconds")
print(f"Queries Delay: {queries_delay} seconds")
print(f"Next Battery Delay: {next_battery_delay} seconds")
print(f"Read Timeout: {read_timeout} seconds")
print(f"...")
print(f"MQTT Broker: {mqtt_broker}, Port: {mqtt_port}, Username: {mqtt_username}, Password: **********  ")
print(f"...")

# Initialize MQTT client
client = mqtt.Client(protocol=mqtt.MQTTv311)
client.username_pw_set(mqtt_username, mqtt_password)
client.connect(mqtt_broker, mqtt_port, 60)
client.loop_start()

def on_disconnect(client, userdata, rc):
    print("MQTT Disconnected. Reconnecting...")
    client.reconnect()

client.on_disconnect = on_disconnect

# ethernet rs485 device
if 'rs485gate_ip' in config:
    TCP_IP = config['rs485gate_ip']
else:
    sys.exit("rs485gate_ip not found in config file")

if 'rs485gate_port' in config:
    TCP_PORT = config['rs485gate_port']
#    TCP_PORT = config.get('rs485gate_port', 50500)
else:
    sys.exit("rs485gate_port not found in config file")

BUFFER_SIZE = 4096

# Add a setting for the number of batteries
num_batteries = config.get('num_batteries', 1)  # Default to 1 battery if not specified

# Processing helper functions
def validate_response_length(response, expected_length):
    return len(response) == expected_length

def hex_to_temperature(hex_string):
    hex_values = [hex_string[i:i+2] for i in range(0, len(hex_string), 2)]
    raw_values = hex_values[3:-2]
    if len(raw_values) % 2 != 0:
        raw_values = raw_values[:-1]
    temperature_pairs = [raw_values[i] + raw_values[i+1] for i in range(0, len(raw_values), 2)]
    raw_decimal_values = [int(pair, 16) if pair else None for pair in temperature_pairs]
    return [round((v - 726) * 0.1 + 22.6, 1) if v is not None else None for v in raw_decimal_values]

def is_valid_temperature(temp):
    return temp is not None and temp_min_limit <= temp <= temp_max_limit

def process_extra_temperature_data(battery_num, temperature_data):
    temperature_hex = binascii.hexlify(temperature_data)
    temps = hex_to_temperature(temperature_hex.decode('utf-8'))
    temps = [t for t in temps if is_valid_temperature(t)]
    return (temps + [None, None])[:2] if temps else (None, None)

def process_battery_data(battery_num, block_voltage, cells_voltage, temperature_data):
    voltage = charged = cycle = current = wattage = None
    cells = temps = None
    if block_voltage:
        hv = binascii.hexlify(block_voltage)
        current_hex = hv[6:-64]
        voltage_hex = hv[10:-60]
        charged_hex = hv[14:-56]
        cycle_hex = hv[34:-36]
        voltage = round(int(voltage_hex, 16) / 100, 2)
        charged = round(int(charged_hex, 16) / 10, 1)
        current_val = int(current_hex, 16)
        if current_val >= 0x8000:
            current_val -= 0x10000
        current = round(current_val / 100, 2)
        cycle = int(cycle_hex, 16)
        wattage = round(current * voltage, 2)
        print(f"Battery {battery_num} SOC: {voltage} V, Charged: {charged} %, Cycles: {cycle}, Current: {current} A, Power: {wattage} W")
    if cells_voltage and len(cells_voltage) == 37 and cells_voltage[0] == battery_num:
        hv = binascii.hexlify(cells_voltage)
        cells = [int(hv[6 + i*4:10 + i*4], 16) for i in range(16)]
        cells = [v if cell_min_limit <= v <= cell_max_limit else None for v in cells]
        if len([c for c in cells if c is not None]) < 8:
#            print(f"SKIP Battery {battery_num}: Bad queries answers and parsing.")
            cells = None
        else:
            print(f"Battery {battery_num} Cell Voltages: {', '.join(str(v) if v else 'X' for v in cells)}")
    if temperature_data:
        hv = binascii.hexlify(temperature_data)
        temps = [t for t in hex_to_temperature(hv.decode('utf-8')) if is_valid_temperature(t)]
    return voltage, charged, cycle, cells, temps, current, wattage

# Function for MQTT Sensors announcements
def announce_battery_sensors(client, battery_index, battery_data):
    device_id = f"ritar_{battery_index}"
    topic_prefix = f"homeassistant/sensor/{device_id}"
    friendly_device_name = f"Ritar Battery {battery_index}"

    def publish_sensor(sensor_suffix, friendly_name, device_class, unit, value, state_class=None):
        unique_id = f"{device_id}_{sensor_suffix}"
        config_topic = f"{topic_prefix}/{sensor_suffix}/config"
        state_topic = f"{topic_prefix}/{sensor_suffix}"

        payload = {
            "name": friendly_name,            # Friendly display name
            "object_id": unique_id,           # Controls entity_id
            "state_topic": state_topic,
            "device_class": device_class,
            "unit_of_measurement": unit,
            "value_template": "{{ value_json.state }}",
            "unique_id": unique_id,
            "device": {
                "identifiers": [device_id],
                "name": friendly_device_name,
                "model": battery_model,
                "manufacturer": "Ritar"
            }
        }
        
        # If a state_class is passed, add it to the payload
        if state_class:
            payload["state_class"] = state_class

        # Publish the configuration and the state
        client.publish(config_topic, json.dumps(payload), retain=True)
        client.publish(state_topic, json.dumps({"state": value}), retain=True)

    # Base sensors
    publish_sensor("voltage", "Voltage", "voltage", "V", battery_data["voltage"])
    publish_sensor("soc", "SOC", "battery", "%", battery_data["soc"])
    publish_sensor("current", "Current", "current", "A", battery_data["current"])
    publish_sensor("power", "Power", "power", "W", battery_data["power"])

    # Handle Cycle Count with validation
    cycle_count = battery_data["cycle"]

    # Ensure the cycle count is a valid integer
    if isinstance(cycle_count, int):
        # Only update if the cycle count is valid and integer
        last_valid_cycle_count[battery_index] = cycle_count
        publish_sensor("cycle", "Cycle Count", None, None, cycle_count, state_class="total_increasing")
    else:
        # If invalid or "unknown", retain the last valid cycle count
        if battery_index in last_valid_cycle_count:
            cycle_count = last_valid_cycle_count[battery_index]
            publish_sensor("cycle", "Cycle Count", None, None, cycle_count, state_class="total_increasing")
        else:
            # No valid cycle count yet, set it to a default value or ignore update
            print(f"Invalid cycle count: {cycle_count}. Retaining previous valid value.")

    # Cells
    for i, cell_voltage in enumerate(battery_data.get("cells", []), start=1):
        publish_sensor(f"cell_{i}", f"Cell {i}", "voltage", "mV", cell_voltage)

    # Temps (regular)
    for i, temp in enumerate(battery_data.get("temps", []), start=1):
        suffix = f"temp_{i}"  # sensor.ritar_1_temp_1, etc.
        name = f"Temp {i}"
        publish_sensor(suffix, name, "temperature", "°C", temp)

    # Special temp sensors
    if battery_data.get("mos_temp") is not None:
        publish_sensor("temp_mos", "T MOS", "temperature", "°C", battery_data["mos_temp"])

    if battery_data.get("env_temp") is not None:
        publish_sensor("temp_env", "T ENV", "temperature", "°C", battery_data["env_temp"])

# Main loop
while True:
    time.sleep(read_timeout)
    try:
        print("Connect to RS485 Ethernet Gate:", TCP_IP, ":", TCP_PORT)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(connection_timeout)
        s.connect((TCP_IP, TCP_PORT))
        print("RS485 Ethernet Gate CONNECTED")
        print("-" * 119)

        battery_queries = {
            1: {"block_voltage": bat_1_get_block_voltage, "cells_voltage": bat_1_get_cells_voltage, "temperature": bat_1_get_temperature, "extra_temperature": bat_1_get_extra_temperature},
            2: {"block_voltage": bat_2_get_block_voltage, "cells_voltage": bat_2_get_cells_voltage, "temperature": bat_2_get_temperature, "extra_temperature": bat_2_get_extra_temperature},
            3: {"block_voltage": bat_3_get_block_voltage, "cells_voltage": bat_3_get_cells_voltage, "temperature": bat_3_get_temperature, "extra_temperature": bat_3_get_extra_temperature},
            4: {"block_voltage": bat_4_get_block_voltage, "cells_voltage": bat_4_get_cells_voltage, "temperature": bat_4_get_temperature, "extra_temperature": bat_4_get_extra_temperature},
            5: {"block_voltage": bat_5_get_block_voltage, "cells_voltage": bat_5_get_cells_voltage, "temperature": bat_5_get_temperature, "extra_temperature": bat_5_get_extra_temperature},
            6: {"block_voltage": bat_6_get_block_voltage, "cells_voltage": bat_6_get_cells_voltage, "temperature": bat_6_get_temperature, "extra_temperature": bat_6_get_extra_temperature},
            7: {"block_voltage": bat_7_get_block_voltage, "cells_voltage": bat_7_get_cells_voltage, "temperature": bat_7_get_temperature, "extra_temperature": bat_7_get_extra_temperature},
            8: {"block_voltage": bat_8_get_block_voltage, "cells_voltage": bat_8_get_cells_voltage, "temperature": bat_8_get_temperature, "extra_temperature": bat_8_get_extra_temperature},
            9: {"block_voltage": bat_9_get_block_voltage, "cells_voltage": bat_9_get_cells_voltage, "temperature": bat_9_get_temperature, "extra_temperature": bat_9_get_extra_temperature},
            10: {"block_voltage": bat_10_get_block_voltage, "cells_voltage": bat_10_get_cells_voltage, "temperature": bat_10_get_temperature, "extra_temperature": bat_10_get_extra_temperature},
            11: {"block_voltage": bat_11_get_block_voltage, "cells_voltage": bat_11_get_cells_voltage, "temperature": bat_11_get_temperature, "extra_temperature": bat_11_get_extra_temperature},
            12: {"block_voltage": bat_12_get_block_voltage, "cells_voltage": bat_12_get_cells_voltage, "temperature": bat_12_get_temperature, "extra_temperature": bat_12_get_extra_temperature},
            13: {"block_voltage": bat_13_get_block_voltage, "cells_voltage": bat_13_get_cells_voltage, "temperature": bat_13_get_temperature, "extra_temperature": bat_13_get_extra_temperature},
            14: {"block_voltage": bat_14_get_block_voltage, "cells_voltage": bat_14_get_cells_voltage, "temperature": bat_14_get_temperature, "extra_temperature": bat_14_get_extra_temperature},
            15: {"block_voltage": bat_15_get_block_voltage, "cells_voltage": bat_15_get_cells_voltage, "temperature": bat_15_get_temperature, "extra_temperature": bat_15_get_extra_temperature},
            16: {"block_voltage": bat_16_get_block_voltage, "cells_voltage": bat_16_get_cells_voltage, "temperature": bat_16_get_temperature, "extra_temperature": bat_16_get_extra_temperature},
        }

        for i in range(1, num_batteries + 1):
            queries = battery_queries[i]
            if i > 1:
                time.sleep(next_battery_delay)

            time.sleep(queries_delay)
            s.send(queries["block_voltage"])
            block_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(block_voltage, 37):
                block_voltage = None

            time.sleep(queries_delay)
            s.send(queries["cells_voltage"])
            cells_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(cells_voltage, 37):
                cells_voltage = None

            time.sleep(queries_delay)
            s.send(queries["temperature"])
            temperature = s.recv(BUFFER_SIZE)
            if not validate_response_length(temperature, 13):
                temperature = None

            extra_temperature = None
            if temperature:
                time.sleep(queries_delay)
                s.send(queries["extra_temperature"])
                extra_temperature = s.recv(BUFFER_SIZE)
                if not validate_response_length(extra_temperature, 25):
                    extra_temperature = None

            mos_temp = env_temp = None
            if extra_temperature:
                mos_temp, env_temp = process_extra_temperature_data(i, extra_temperature)

            voltage, charged, cycle, cells, temps, current, wattage = process_battery_data(i, block_voltage, cells_voltage, temperature)

            if temps:
                print(f"Battery {i} Temperatures: {', '.join(map(str, temps))}°C")
            if mos_temp is not None and env_temp is not None:
                print(f"Battery {i} MOS Temperature: {mos_temp}°C , Environment Temperature: {env_temp}°C")
                print("-" * 119)

            if voltage and cells and volt_min_limit <= voltage <= volt_max_limit and cell_min_limit <= cells[0] <= cell_max_limit:
                battery_data = {
                    "voltage": voltage,
                    "soc": charged,
                    "cycle": cycle,
                    "current": current,
                    "power": wattage,
                    "cells": cells,
                    "temps": temps,
                    "mos_temp": mos_temp,
                    "env_temp": env_temp
                }
                announce_battery_sensors(client, i, battery_data)

        s.close()

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(read_timeout)
