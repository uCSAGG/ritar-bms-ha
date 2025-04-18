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

warnings.filterwarnings("ignore", category=DeprecationWarning)

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
def validate_queries_delay(queries_delay, extra_queries_delay, next_battery_delay):
    def convert_to_float(value, name):
        if isinstance(value, str):
            value = value.replace(",", ".")
        try:
            return float(value)
        except ValueError:
            print(f"Error: '{name}' must be a valid number. Found: {value}")
            sys.exit(1)

    queries_delay = convert_to_float(queries_delay, "queries_delay")
    extra_queries_delay = convert_to_float(extra_queries_delay, "extra_queries_delay")
    next_battery_delay = convert_to_float(next_battery_delay, "next_battery_delay")

    return queries_delay, extra_queries_delay, next_battery_delay

# Load the configuration
config = load_config()

# Ritar Battery Model
battery_model = config.get('battery_model', 'BAT-5KWH-51.2V')

# Get values from the configuration, with defaults where necessary
read_timeout = config.get('read_timeout', 30)  # Default to 30 seconds if not specified
connection_timeout = config.get('connection_timeout', 3)  # Default to 3 seconds if not specified

# Fetch values from config with defaults
queries_delay = config.get('queries_delay', '0.1')  # Default to '0.1' if not specified
extra_queries_delay = config.get('extra_queries_delay', '0.1')  # Default to '0.1' if not specified
next_battery_delay = config.get('next_battery_delay', '0.5')  # Default to '0.5' if not specified

# MQTT connection parameters (load from config if needed)
mqtt_broker = config.get("mqtt_broker", "core-mosquitto")
mqtt_port = config.get("mqtt_port", 1883)
mqtt_username = config.get("mqtt_username", "homeassistant")
mqtt_password = config.get("mqtt_password", "mqtt_password_here")

# Validate and convert all three
queries_delay, extra_queries_delay, next_battery_delay = validate_queries_delay(
    queries_delay, extra_queries_delay, next_battery_delay
)

# Print the config values for confirmation
print(f"...")
print(f"RS485 to Ethernet Gate...")
print(f"IP Address: {config['rs485gate_ip']}")
print(f"Port: {config['rs485gate_port']} ")
print(f"...")
print(f"Connection Timeout: {connection_timeout} seconds")
print(f"Queries Delay: {queries_delay} seconds")
print(f"Extra Queries Delay: {extra_queries_delay} seconds")
print(f"Next Battery Delay: {next_battery_delay} seconds")
print(f"Read Timeout: {read_timeout} seconds")
print(f"...")
print(f"MQTT...")
print(f"...")
print(f"Broker: {mqtt_broker}, Port: {mqtt_port}, Username: {mqtt_username}, Password: **********  ")
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


###########################################
########## network RS485 gateway ##########
###########################################

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

# Battery 1 Queries
bat_1_get_block_voltage = b'\x01\x03\x00\x00\x00\x10\x44\x06'  # Battery voltage query for Battery 1
bat_1_not_decrypted_1 = b'\x01\x03\x00\x21\x00\x01\xd4\x00'  # Unknown at now
bat_1_get_cells_voltage = b'\x01\x03\x00\x28\x00\x10\xc4\x0e'  # Cells voltage query for Battery 1
bat_1_get_temperature = b'\x01\x03\x00\x78\x00\x04\xc4\x10'  # Temperature query for Battery 1
bat_1_not_decrypted_2 = b'\x01\x03\x00\x9b\x00\x02\xb5\xe4'  # Unknown at now
bat_1_get_extra_temperature = b'\x01\x03\x00\x91\x00\x0a\x94\x20'  # Extra temperature query for Battery 1
bat_1_not_decrypted_3 = b'\x01\x03\x00\xef\x00\x06\xf4\x3d'  # Unknown at now

# Battery 2 Queries
bat_2_get_block_voltage = b'\x02\x03\x00\x00\x00\x10\x44\x35'  # Battery voltage query for Battery 2
bat_2_not_decrypted_1 = b'\x02\x03\x00\x21\x00\x01\xd4\x33'  # Unknown at now
bat_2_get_cells_voltage = b'\x02\x03\x00\x28\x00\x10\xc4\x3d'  # Cells voltage query for Battery 2
bat_2_get_temperature = b'\x02\x03\x00\x78\x00\x04\xc4\x23'  # Temperature query for Battery 2
bat_2_not_decrypted_2 = b'\x02\x03\x00\x9b\x00\x02\xb5\xd7'  # Unknown at now
bat_2_get_extra_temperature = b'\x02\x03\x00\x91\x00\x0a\x94\x13'  # Extra temperature query for Battery 2
bat_2_not_decrypted_3 = b'\x02\x03\x00\xef\x00\x06\xf4\x0e'  # Unknown at now

# Battery 3 Queries
bat_3_get_block_voltage = b'\x03\x03\x00\x00\x00\x10\x45\xe4'  # Battery voltage query for Battery 3
bat_3_not_decrypted_1 = b'\x03\x03\x00\x21\x00\x01\xd5\xe2'  # Unknown at now
bat_3_get_cells_voltage = b'\x03\x03\x00\x28\x00\x10\xc5\xec'  # Cells voltage query for Battery 3
bat_3_get_temperature = b'\x03\x03\x00\x78\x00\x04\xc5\xf2'  # Temperature query for Battery 3
bat_3_not_decrypted_2 = b'\x03\x03\x00\x9b\x00\x02\xb4\x06'  # Unknown at now
bat_3_get_extra_temperature = b'\x03\x03\x00\x91\x00\x0a\x95\xc2'  # Extra temperature query for Battery 3
bat_3_not_decrypted_3 = b'\x03\x03\x00\xef\x00\x06\xf5\xdf'  # Unknown at now

# Battery 4 Queries
bat_4_get_block_voltage = b'\x04\x03\x00\x00\x00\x10\x44\x53'  # Battery voltage query for Battery 4
bat_4_not_decrypted_1 = b'\x04\x03\x00\x21\x00\x01\xd4\x55'  # Unknown at now
bat_4_get_cells_voltage = b'\x04\x03\x00\x28\x00\x10\xc4\x5b'  # Cells voltage query for Battery 4
bat_4_get_temperature = b'\x04\x03\x00\x78\x00\x04\xc4\x45'  # Temperature query for Battery 4
bat_4_not_decrypted_2 = b'\x04\x03\x00\x9b\x00\x02\xb5\xb1'  # Unknown at now
bat_4_get_extra_temperature = b'\x04\x03\x00\x91\x00\x0a\x94\x75'  # Extra temperature query for Battery 4
bat_4_not_decrypted_3 = b'\x04\x03\x00\xef\x00\x06\xf4\x68'  # Unknown at now

# Function to validate response length
def validate_response_length(response, expected_length):
    if len(response) != expected_length:
#        print(f"Error: Invalid response length! Expected {expected_length} bytes, got {len(response)} bytes.")
        return False
    return True

# Function to validate ping response
#def validate_ping_response(response, battery_num):
#    if battery_num == 1:
#        valid_response = b'\x01\x03\x02\xfa\xaf\xba\x98'
#    elif battery_num == 2:
#        valid_response = b'\x02\x03\x02\xfa\xaf\xfe\x98'
#    else:
#        print("Invalid battery number")
#        return False

#    if response == valid_response:
#        print(f"Battery {battery_num} Ping Successful")
#        return True
#    else:
#        print(f"Battery {battery_num} Ping Failed")
#        return False

# Hex to temperature conversion function
def hex_to_temperature(hex_string):
    # Step 1: Parse the hex string into a list of two-byte chunks
    hex_values = [hex_string[i:i+2] for i in range(0, len(hex_string), 2)]

    # Ignore the first three and last two bytes (headers and footer)
    raw_values = hex_values[3:-2]

    # Step 2: Group the raw values into pairs of 2 bytes (representing each temperature sensor)
    if len(raw_values) % 2 != 0:
        print("Warning: Raw values contain an odd number of elements. Dropping the last element.")
        raw_values = raw_values[:-1]  # Drop the last element if it's unpaired

    temperature_pairs = [raw_values[i] + raw_values[i+1] for i in range(0, len(raw_values), 2)]

    # Step 3: Convert each pair (hex) into a decimal value, skipping empty or invalid hex pairs
    raw_decimal_values = []
    for temp_pair in temperature_pairs:
        if temp_pair:  # Check if the temp_pair is not empty
            try:
                raw_decimal_values.append(int(temp_pair, 16))
            except ValueError as e:
                print(f"Error converting hex to decimal for pair {temp_pair}: {e}")
                raw_decimal_values.append(None)  # Append None in case of conversion failure
        else:
            print(f"Skipping empty hex pair: {temp_pair}")
            raw_decimal_values.append(None)

    # Step 4: Apply the scaling algorithm for each sensor and round to 1 decimal place
    temperatures = []
    for value in raw_decimal_values:
        if value is not None:
            # Apply the scaling formula and round to 1 decimal place
            temperature = round((value - 726) * 0.1 + 22.6, 1)
            temperatures.append(temperature)
        else:
            temperatures.append(None)  # Append None if there was a conversion error

    return temperatures

# Function to check if a temperature is within a valid range
def is_valid_temperature(temp):
    if temp is None:
        return False
    if temp < -50 or temp > 70:
        return False
    return True

##################################################
############### MQTT Procedures ##################
##################################################

# Let's assume we have a global dictionary to store the last valid cycle count value
last_valid_cycle_count = {}

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

# Main infinite loop
while True:
    time.sleep(read_timeout)  # Use the timeout value from the config.yaml
    try:
        ##########################################
        ########## open stream to RS485 ##########
        ##########################################
        try:
            print("Connect to RS485 Ethernet Gate: ", TCP_IP, ":", TCP_PORT)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(connection_timeout)  # Set the connection timeout from the config.yaml
            s.connect((TCP_IP, TCP_PORT))
            print("RS485 Ethernet Gate CONNECTED")
            print("-----------------------------------------------------------------------------------------------------------------------")
        except OSError as msg:
            print(f"RS485 Ethernet Gate connection ERROR: {msg}")
            time.sleep(30)
            continue

        ## Ping Battery 1
        #time.sleep(1)
        #s.send(bat_1_not_decrypted_1)
        #ping_battery_1_response = s.recv(BUFFER_SIZE)
        #if not validate_ping_response(ping_battery_1_response, 1):
        #    print("Invalid response for Battery 1 Ping, skipping...")
        #    continue

        # Query for Battery 1 Block Voltage
        time.sleep(queries_delay)
        s.send(bat_1_get_block_voltage)
        bat_1_block_voltage = s.recv(BUFFER_SIZE)
        if not validate_response_length(bat_1_block_voltage, 37):
#            print("Invalid response for battery #1 block voltage, skipping...")
            bat_1_block_voltage = None

        # Query for Battery 1 Cells Voltage
        time.sleep(queries_delay)
        s.send(bat_1_get_cells_voltage)
        bat_1_cells_voltage = s.recv(BUFFER_SIZE)
        if not validate_response_length(bat_1_cells_voltage, 37):
#            print("Invalid response for battery #1 cells voltage, skipping...")
            bat_1_cells_voltage = None

        # Query for Battery 1 Temperature
        time.sleep(queries_delay)
        s.send(bat_1_get_temperature)
        bat_1_temperature = s.recv(BUFFER_SIZE)
        if not validate_response_length(bat_1_temperature, 13):
#            print("Invalid response for battery #1 temperature, skipping...")
            bat_1_temperature = None

        # Now, only query for Extra Temperature if the regular temperature response was successful
        if bat_1_temperature:
            time.sleep(extra_queries_delay)
            s.send(bat_1_get_extra_temperature)
            bat_1_extra_temperature = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_1_extra_temperature, 25):
#                print("Invalid response for Battery #1 extra temperature, skipping...")
                bat_1_extra_temperature = None

        # Query for Battery 2 if available
        if num_batteries > 1:

            ## Ping Battery 2
            time.sleep(next_battery_delay)
            #s.send(bat_2_not_decrypted_1)
            #ping_battery_2_response = s.recv(BUFFER_SIZE)
            #if not validate_ping_response(ping_battery_2_response, 2):
            #    print("Invalid response for Battery 2 Ping, skipping...")
            #    continue

            # Query for Battery 2 Block Voltage
            time.sleep(queries_delay)
            s.send(bat_2_get_block_voltage)
            bat_2_block_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_2_block_voltage, 37):
#                print("Invalid response for battery #2 block voltage, skipping...")
                bat_2_block_voltage = None

            # Query for Battery 2 Cells Voltage
            time.sleep(queries_delay)
            s.send(bat_2_get_cells_voltage)
            bat_2_cells_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_2_cells_voltage, 37):
#                print("Invalid response for battery #2 cells voltage, skipping...")
                bat_2_cells_voltage = None

            # Query for Battery 2 Temperature
            time.sleep(queries_delay)
            s.send(bat_2_get_temperature)
            bat_2_temperature = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_2_temperature, 13):
#                print("Invalid response for battery #2 temperature, skipping...")
                bat_2_temperature = None

            # Now, only query for Extra Temperature if the regular temperature response was successful
            if bat_2_temperature:
                time.sleep(extra_queries_delay)
                s.send(bat_2_get_extra_temperature)
                bat_2_extra_temperature = s.recv(BUFFER_SIZE)
                if not validate_response_length(bat_2_extra_temperature, 25):
#                    print("Invalid response for Battery #2 extra temperature, skipping...")
                    bat_2_extra_temperature = None

        # Query for Battery 3 if available
        if num_batteries > 2:

            ## Ping Battery 3
            time.sleep(next_battery_delay)
            #s.send(bat_3_not_decrypted_1)
            #ping_battery_3_response = s.recv(BUFFER_SIZE)
            #if not validate_ping_response(ping_battery_3_response, 3):
            #    print("Invalid response for Battery 3 Ping, skipping...")
            #    continue

            # Query for Battery 3 Block Voltage
            time.sleep(queries_delay)
            s.send(bat_3_get_block_voltage)
            bat_3_block_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_3_block_voltage, 37):
#                print("Invalid response for battery #3 block voltage, skipping...")
                bat_3_block_voltage = None

            # Query for Battery 3 Cells Voltage
            time.sleep(queries_delay)
            s.send(bat_3_get_cells_voltage)
            bat_3_cells_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_3_cells_voltage, 37):
#                print("Invalid response for battery #3 cells voltage, skipping...")
                bat_3_cells_voltage = None

            # Query for Battery 3 Temperature
            time.sleep(queries_delay)
            s.send(bat_3_get_temperature)
            bat_3_temperature = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_3_temperature, 13):
#                print("Invalid response for battery #3 temperature, skipping...")
                bat_3_temperature = None

            # Now, only query for Extra Temperature if the regular temperature response was successful
            if bat_3_temperature:
                time.sleep(extra_queries_delay)
                s.send(bat_3_get_extra_temperature)
                bat_3_extra_temperature = s.recv(BUFFER_SIZE)
                if not validate_response_length(bat_3_extra_temperature, 25):
#                    print("Invalid response for Battery #3 extra temperature, skipping...")
                    bat_3_extra_temperature = None

        # Query for Battery 4 if available
        if num_batteries > 3:

            ## Ping Battery 4
            time.sleep(next_battery_delay)
            #s.send(bat_4_not_decrypted_1)
            #ping_battery_4_response = s.recv(BUFFER_SIZE)
            #if not validate_ping_response(ping_battery_4_response, 4):
            #    print("Invalid response for Battery 4 Ping, skipping...")
            #    continue

            # Query for Battery 4 Block Voltage
            time.sleep(queries_delay)
            s.send(bat_4_get_block_voltage)
            bat_4_block_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_4_block_voltage, 37):
#                print("Invalid response for battery #4 block voltage, skipping...")
                bat_4_block_voltage = None

            # Query for Battery 4 Cells Voltage
            time.sleep(queries_delay)
            s.send(bat_4_get_cells_voltage)
            bat_4_cells_voltage = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_4_cells_voltage, 37):
#                print("Invalid response for battery #4 cells voltage, skipping...")
                bat_4_cells_voltage = None

            # Query for Battery 4 Temperature
            time.sleep(queries_delay)
            s.send(bat_4_get_temperature)
            bat_4_temperature = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_4_temperature, 13):
#                print("Invalid response for battery #4 temperature, skipping...")
                bat_4_temperature = None

            # Now, only query for Extra Temperature if the regular temperature response was successful
            if bat_4_temperature:
                time.sleep(extra_queries_delay)
                s.send(bat_4_get_extra_temperature)
                bat_4_extra_temperature = s.recv(BUFFER_SIZE)
                if not validate_response_length(bat_4_extra_temperature, 25):
#                    print("Invalid response for Battery #4 extra temperature, skipping...")
                    bat_4_extra_temperature = None

        # Close RS485 stream
        s.close()

        #####################################
        ########## Battery Processing #######
        #####################################
        # Static variables for checking voltages and cells
        cell_min_limit = 2450
        cell_max_limit = 4750
        volt_min_limit = 40.00
        volt_max_limit = 60.00
        
        def process_battery_data(battery_num, block_voltage, cells_voltage, temperature_data):
            if block_voltage is not None:
                # Process block voltage and cells voltage for each battery
                block_voltage_hex = binascii.hexlify(block_voltage)
                current_hex = block_voltage_hex[6:-64]
                voltage_hex = block_voltage_hex[10:-60]
                charged_hex = block_voltage_hex[14:-56]
                cycle_hex = block_voltage_hex[34:-36]
        
                voltage_dec = int(voltage_hex, 16)
                charged_dec = int(charged_hex, 16)
                cycle_dec = int(cycle_hex, 16)
                current_dec = int(current_hex, 16)
        
                if current_dec >= 0x8000:  # Check if the value is greater than or equal to 32768 (two's complement for negative numbers)
                    current_dec -= 0x10000  # Convert to signed decimal using two's complement

                # Format SOC, Current, and Charged percentage
                formatted_voltage = round(voltage_dec / 100, 2)  # Dividing by 100 to get the correct voltage (e.g., 5399 -> 53.99)
                formatted_current = round(current_dec / 100, 2)  # Dividing by 100 to get the current in A
                formatted_charged = round(charged_dec / 10, 1)    # Dividing by 10 to get the charged percentage (e.g., 1000 -> 100.0)

                # Calculate wattage (power in watts)
                wattage = round(formatted_current * formatted_voltage, 2)  # Voltage * Current, both in correct units

                print(f"Battery {battery_num} SOC: {formatted_voltage} V, Charged: {formatted_charged} %, Cycles: {cycle_dec}, Current: {formatted_current} A, Power: {wattage} W")

            if cells_voltage is not None:
                cells_voltage_hex = binascii.hexlify(cells_voltage)
                cells = []
                for i in range(16):
                    cell_hex = cells_voltage_hex[6 + (i * 4): 10 + (i * 4)]
                    cells.append(int(cell_hex, 16))
                print(f"Battery {battery_num} Cell Voltages: {', '.join(map(str, cells))}")

            if temperature_data is not None:
                temperature_hex = binascii.hexlify(temperature_data)
                temperatures = hex_to_temperature(temperature_hex.decode('utf-8'))

                # Filter out defective temperatures
                temperatures = [temp for temp in temperatures if is_valid_temperature(temp)]

     #           if temperatures:
     #               print(f"Battery {battery_num} Temperatures: {', '.join(map(str, temperatures))}°C")

            return formatted_voltage, formatted_charged, cycle_dec, cells, temperatures, formatted_current, wattage


        def process_extra_temperature_data(battery_num, temperature_data):
            if temperature_data is not None:
                temperature_hex = binascii.hexlify(temperature_data)
                temperatures = hex_to_temperature(temperature_hex.decode('utf-8'))

                # Filter out defective temperatures
                temperatures = [temp for temp in temperatures if is_valid_temperature(temp)]

                if temperatures:
                    mos_temperature = temperatures[0]  # First temperature pair for MOS
                    env_temperature = temperatures[1]  # Second temperature pair for environment
    #                print(f"Battery {battery_num} MOS Temperature: {mos_temperature}°C , Environment Temperature: {env_temperature}°C")
                    return mos_temperature, env_temperature
            return None, None

        # Process Battery 1 Extra Temperatures
        if bat_1_extra_temperature:
            bat_1_mos_temp, bat_1_env_temp = process_extra_temperature_data(1, bat_1_extra_temperature)

        # Process Battery 1 Temperatures
        bat_1_voltage, bat_1_charged, bat_1_cycle, bat_1_cells, bat_1_temps, bat_1_current, bat_1_wattage = process_battery_data(1, bat_1_block_voltage, bat_1_cells_voltage, bat_1_temperature)

        # Now print Battery 1 Temperatures followed by MOS and Env temperatures
        if bat_1_temps:
            print(f"Battery 1 Temperatures: {', '.join(map(str, bat_1_temps))}°C")
        if bat_1_mos_temp is not None and bat_1_env_temp is not None:
            print(f"Battery 1 MOS Temperature: {bat_1_mos_temp}°C , Environment Temperature: {bat_1_env_temp}°C")
            print("-----------------------------------------------------------------------------------------------------------------------")

        # Process Battery 2 Extra Temperatures (if available)
        if num_batteries > 1 and bat_2_extra_temperature:
            bat_2_mos_temp, bat_2_env_temp = process_extra_temperature_data(2, bat_2_extra_temperature)

        # Process Battery 2 Temperatures
        if num_batteries > 1:
            bat_2_voltage, bat_2_charged, bat_2_cycle, bat_2_cells, bat_2_temps, bat_2_current, bat_2_wattage = process_battery_data(2, bat_2_block_voltage, bat_2_cells_voltage, bat_2_temperature)

            # Now print Battery 2 Temperatures followed by MOS and Env temperatures
            if bat_2_temps:
                print(f"Battery 2 Temperatures: {', '.join(map(str, bat_2_temps))}°C")
            if bat_2_mos_temp is not None and bat_2_env_temp is not None:
                print(f"Battery 2 MOS Temperature: {bat_2_mos_temp}°C , Environment Temperature: {bat_2_env_temp}°C")
                print("-----------------------------------------------------------------------------------------------------------------------")

        # Process Battery 3 Extra Temperatures (if available)
        if num_batteries > 2 and bat_3_extra_temperature:
            bat_3_mos_temp, bat_3_env_temp = process_extra_temperature_data(3, bat_3_extra_temperature)

        # Process Battery 3 Temperatures
        if num_batteries > 2:
            bat_3_voltage, bat_3_charged, bat_3_cycle, bat_3_cells, bat_3_temps, bat_3_current, bat_3_wattage = process_battery_data(3, bat_3_block_voltage, bat_3_cells_voltage, bat_3_temperature)

            # Now print Battery 3 Temperatures followed by MOS and Env temperatures
            if bat_3_temps:
                print(f"Battery 3 Temperatures: {', '.join(map(str, bat_3_temps))}°C")
            if bat_3_mos_temp is not None and bat_3_env_temp is not None:
                print(f"Battery 3 MOS Temperature: {bat_3_mos_temp}°C , Environment Temperature: {bat_3_env_temp}°C")
                print("-----------------------------------------------------------------------------------------------------------------------")

        # Process Battery 4 Extra Temperatures (if available)
        if num_batteries > 3 and bat_4_extra_temperature:
            bat_4_mos_temp, bat_4_env_temp = process_extra_temperature_data(4, bat_4_extra_temperature)

        # Process Battery 4 Temperatures
        if num_batteries > 3:
            bat_4_voltage, bat_4_charged, bat_4_cycle, bat_4_cells, bat_4_temps, bat_4_current, bat_4_wattage = process_battery_data(4, bat_4_block_voltage, bat_4_cells_voltage, bat_4_temperature)

            # Now print Battery 4 Temperatures followed by MOS and Env temperatures
            if bat_4_temps:
                print(f"Battery 4 Temperatures: {', '.join(map(str, bat_4_temps))}°C")
            if bat_4_mos_temp is not None and bat_4_env_temp is not None:
                print(f"Battery 4 MOS Temperature: {bat_4_mos_temp}°C , Environment Temperature: {bat_4_env_temp}°C")
                print("-----------------------------------------------------------------------------------------------------------------------")

        ###################################
        ######## API output ###############
        ###################################
        
        #print(f"TEST Current: {bat_1_current} A , {bat_2_current} A")
        
        # Battery 1
        if volt_min_limit <= bat_1_voltage <= volt_max_limit and cell_min_limit <= bat_1_cells[0] <= cell_max_limit:
            bat_1_data = {
                "voltage": bat_1_voltage,
                "soc": bat_1_charged,
                "cycle": bat_1_cycle,
                "current": bat_1_current,
                "power": bat_1_wattage,
                "cells": bat_1_cells,
                "temps": bat_1_temps,
                "mos_temp": bat_1_mos_temp,
                "env_temp": bat_1_env_temp
            }
            announce_battery_sensors(client, 1, bat_1_data)

        # Battery 2  (if available)
        if num_batteries > 1 and volt_min_limit <= bat_2_voltage <= volt_max_limit and cell_min_limit <= bat_2_cells[0] <= cell_max_limit:
            bat_2_data = {
                "voltage": bat_2_voltage,
                "soc": bat_2_charged,
                "cycle": bat_2_cycle,
                "current": bat_2_current,
                "power": bat_2_wattage,
                "cells": bat_2_cells,
                "temps": bat_2_temps,
                "mos_temp": bat_2_mos_temp,
                "env_temp": bat_2_env_temp
            }
            announce_battery_sensors(client, 2, bat_2_data)

        # Battery 3  (if available)
        if num_batteries > 2 and volt_min_limit <= bat_3_voltage <= volt_max_limit and cell_min_limit <= bat_3_cells[0] <= cell_max_limit:
            bat_3_data = {
                "voltage": bat_3_voltage,
                "soc": bat_3_charged,
                "cycle": bat_3_cycle,
                "current": bat_3_current,
                "power": bat_3_wattage,
                "cells": bat_3_cells,
                "temps": bat_3_temps,
                "mos_temp": bat_3_mos_temp,
                "env_temp": bat_3_env_temp
            }
            announce_battery_sensors(client, 3, bat_3_data)

        # Battery 4  (if available)
        if num_batteries > 3 and volt_min_limit <= bat_4_voltage <= volt_max_limit and cell_min_limit <= bat_4_cells[0] <= cell_max_limit:
            bat_4_data = {
                "voltage": bat_4_voltage,
                "soc": bat_4_charged,
                "cycle": bat_4_cycle,
                "current": bat_4_current,
                "power": bat_4_wattage,
                "cells": bat_4_cells,
                "temps": bat_4_temps,
                "mos_temp": bat_4_mos_temp,
                "env_temp": bat_4_env_temp
            }
            announce_battery_sensors(client, 4, bat_4_data)
            
        # Add the delay before the next iteration
   #     time.sleep(10)

    except Exception as e:
#        print(f"Error: {e}")
        time.sleep(30)
    
