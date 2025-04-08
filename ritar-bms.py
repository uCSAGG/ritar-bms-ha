#!/usr/bin/env python3

import time
import binascii
import socket
import os
import sys
import yaml
import json
import xml.etree.ElementTree as ET

# Function to load configuration from JSON or YAML
def load_config():
    config = {}

    # Check for options.json
    if os.path.exists('/data/options.json'):
        print("Loading options.json")
        with open('/data/options.json', 'r') as file:
            config = json.load(file)
            print("Config loaded from options.json: " + json.dumps(config))

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

# Function to process and validate queries_delay value
def validate_queries_delay(queries_delay):
    if isinstance(queries_delay, str):
        # Replace commas with dots if any
        queries_delay = queries_delay.replace(",", ".")
    
    try:
        # Convert to float, raise error if invalid
        return float(queries_delay)
    except ValueError:
        print(f"Error: 'queries_delay' must be a valid number. Found: {queries_delay}")
        sys.exit(1)  # Exit if invalid value is provided

# Load the configuration
config = load_config()

# Get values from the configuration, with defaults where necessary
read_timeout = config.get('read_timeout', 30)  # Default to 30 seconds if not specified
connection_timeout = config.get('connection_timeout', 3)  # Default to 3 seconds if not specified

# Validate and process queries_delay value
queries_delay = config.get('queries_delay', '0.1')  # Default to '0.1' if not specified
queries_delay = validate_queries_delay(queries_delay)

# Print the config values for confirmation
print(f"Connection Timeout: {connection_timeout} seconds")
print(f"Queries Delay: {queries_delay} seconds")
print(f"Read Timeout: {read_timeout} seconds")

##
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

# Assuming 'bat_1' and 'bat_2' queries are defined
bat_1_get_block_voltage = b'\x01\x03\x00\x00\x00\x10\x44\x06'
bat_1_get_cells_voltage = b'\x01\x03\x00\x28\x00\x10\xc4\x0e'
bat_1_get_temperature = b'\x01\x03\x00\x78\x00\x04\xc4\x10'  # Temperature query for Battery 1
bat_2_get_block_voltage = b'\x02\x03\x00\x00\x00\x10\x44\x35'
bat_2_get_cells_voltage = b'\x02\x03\x00\x28\x00\x10\xc4\x3d'
bat_2_get_temperature = b'\x02\x03\x00\x78\x00\x04\xc4\x23'  # Temperature query for Battery 2
bat_1_get_extra_temperature = b'\x01\x03\x00\x91\x00\x0A\x94\x20'  # Extra temperature query for Battery 1
bat_2_get_extra_temperature = b'\x02\x03\x00\x91\x00\x0A\x94\x13'  # Extra temperature query for Battery 2

# Ping queries for both batteries
ping_battery_1 = b'\x01\x03\x00\x21\x00\x01\xd4\x00'
ping_battery_2 = b'\x02\x03\x00\x21\x00\x01\xd4\x33'

# Function to validate response length
def validate_response_length(response, expected_length):
    if len(response) != expected_length:
#        print(f"Error: Invalid response length! Expected {expected_length} bytes, got {len(response)} bytes.")
        return False
    return True

# Function to validate ping response
def validate_ping_response(response, battery_num):
    if battery_num == 1:
        valid_response = b'\x01\x03\x02\xfa\xaf\xba\x98'
    elif battery_num == 2:
        valid_response = b'\x02\x03\x02\xfa\xaf\xfe\x98'
    else:
        print("Invalid battery number")
        return False

    if response == valid_response:
        print(f"Battery {battery_num} Ping Successful")
        return True
    else:
        print(f"Battery {battery_num} Ping Failed")
        return False

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
    if temp < -20 or temp > 100:
        return False
    return True

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
            time.sleep(15)
            continue

        ## Ping Battery 1
        #time.sleep(1)
        #s.send(ping_battery_1)
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
            time.sleep(0.2)
            s.send(bat_1_get_extra_temperature)
            bat_1_extra_temperature = s.recv(BUFFER_SIZE)
            if not validate_response_length(bat_1_extra_temperature, 25):
#                print("Invalid response for Battery #1 extra temperature, skipping...")
                bat_1_extra_temperature = None

        # Query for Battery 2 if available
        if num_batteries > 1:

            ## Ping Battery 2
            #time.sleep(2)
            #s.send(ping_battery_2)
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
                time.sleep(0.2)
                s.send(bat_2_get_extra_temperature)
                bat_2_extra_temperature = s.recv(BUFFER_SIZE)
                if not validate_response_length(bat_2_extra_temperature, 25):
#                    print("Invalid response for Battery #2 extra temperature, skipping...")
                    bat_2_extra_temperature = None

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

        ###################################
        ######## API output ###############
        ###################################
        
        #print(f"TEST Current: {bat_1_current} A , {bat_2_current} A")
        
        # Handle Battery 1 output
        if volt_min_limit <= bat_1_voltage <= volt_max_limit and cell_min_limit <= bat_1_cells[0] <= cell_max_limit:
            ritar_bms1 = {
                'b1volt': bat_1_voltage,
                'b1soc': bat_1_charged,
                'b1cycl': bat_1_cycle,
                'b1cur': bat_1_current,
                'b1power': bat_1_wattage,
                **{f'b1c{i+1}': bat_1_cells[i] for i in range(16)},
                **{f'b1temp{i+1}': bat_1_temps[i] for i in range(4)},  # Only 4 sensors per battery
            }
            
            # Include MOS and Environment Temperature for Battery 1 if available
            if bat_1_mos_temp is not None and bat_1_env_temp is not None:
                ritar_bms1['b1mos'] = bat_1_mos_temp
                ritar_bms1['b1env'] = bat_1_env_temp

            root = ET.Element('response')
            for key, value in ritar_bms1.items():
                child = ET.SubElement(root, key)
                child.text = str(value)
            tree = ET.ElementTree(root)
            with open('/web_ui/api/ritar-bat-1.xml', 'wb') as file:
                tree.write(file, encoding="utf-8", xml_declaration=False)

        # Handle Battery 2 output (if available)
        if num_batteries > 1 and volt_min_limit <= bat_2_voltage <= volt_max_limit and cell_min_limit <= bat_2_cells[0] <= cell_max_limit:
            ritar_bms2 = {
                'b2volt': bat_2_voltage,
                'b2soc': bat_2_charged,
                'b2cycl': bat_2_cycle,
                'b2cur': bat_2_current,
                'b2power': bat_2_wattage,
                **{f'b2c{i+1}': bat_2_cells[i] for i in range(16)},
                **{f'b2temp{i+1}': bat_2_temps[i] for i in range(4)},  # Only 4 sensors per battery
            }

            # Include MOS and Environment Temperature for Battery 2 if available
            if bat_2_mos_temp is not None and bat_2_env_temp is not None:
                ritar_bms2['b2mos'] = bat_2_mos_temp
                ritar_bms2['b2env'] = bat_2_env_temp

            root = ET.Element('response')
            for key, value in ritar_bms2.items():
                child = ET.SubElement(root, key)
                child.text = str(value)
            tree = ET.ElementTree(root)
            with open('/web_ui/api/ritar-bat-2.xml', 'wb') as file:
                tree.write(file, encoding="utf-8", xml_declaration=False)

        # Add the delay before the next iteration
   #     time.sleep(10)

    except Exception as e:
#        print(f"Error: {e}")
        time.sleep(15)
    
