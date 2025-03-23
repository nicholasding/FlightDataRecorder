import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

def find_ground_level(altitude_data, window_size=20):
    """
    Find ground level by:
    1. Skip first 5 data points
    2. Using a rolling window to find periods of stable readings
    3. Looking for clusters of similar altitude readings
    4. Taking the mean of the most common cluster as ground level
    """
    # Calculate standard deviation in rolling windows
    rolling_std = pd.Series(altitude_data).rolling(window_size).std()
    
    # Find stable periods (where std dev is small)
    stable_mask = rolling_std < 0.5
    stable_points = altitude_data[stable_mask]
    
    # Round to nearest 0.5m to find clusters
    rounded = np.round(stable_points * 2) / 2
    
    return rounded.mode()[0]

def find_flight_period(df, ground_level, threshold=1.0):
    """
    Detect flight start and end using apogee as reference:
    1. Find apogee (peak altitude)
    2. Walk backwards from apogee to find launch point
    3. Walk forwards from apogee to find landing point
    """
    calibrated_altitude = df['Calibrated_Altitude']
    
    # Find apogee
    apogee_idx = calibrated_altitude.idxmax()
    apogee_altitude = calibrated_altitude[apogee_idx]
    
    # Walk backwards from apogee to find launch
    launch_threshold = threshold  # meters above ground
    for i in range(apogee_idx, 0, -1):
        if calibrated_altitude[i] <= launch_threshold:
            flight_start = i
            break
    else:
        flight_start = 0
    
    # Walk forwards from apogee to find landing
    landing_threshold = threshold  # meters above ground
    for i in range(apogee_idx, len(calibrated_altitude)):
        if calibrated_altitude[i] <= landing_threshold:
            flight_end = i
            break
    else:
        flight_end = len(calibrated_altitude) - 1
    
    # Add some margin to capture full launch and landing
    flight_start = max(0, flight_start - 10)  # 0.5 seconds before detected launch
    flight_end = min(len(calibrated_altitude) - 1, flight_end)  # 0.5 seconds after detected landing
    
    print(f"Apogee at index: {apogee_idx}, altitude: {apogee_altitude:.1f}m")
    
    return flight_start, flight_end

def plot_altitude_data(csv_path):
    try:
        # Read CSV file and immediately drop first 5 rows
        df = pd.read_csv(csv_path).iloc[5:]
        df = df.reset_index(drop=True)
        
        # Convert timestamp to seconds
        df['Time'] = df['Timestamp'] / 1000.0
        
        # Find ground level and calibrate altitude
        ground_level = find_ground_level(df['Altitude(m)'])
        df['Calibrated_Altitude'] = df['Altitude(m)'] - ground_level
        df['Altitude_ft'] = df['Calibrated_Altitude'] * 3.28084  # For display only
        
        # Find flight period
        flight_start, flight_end = find_flight_period(df, ground_level)
        print(f"Flight start: {flight_start}, Flight end: {flight_end}")
        
        # Get flight data and normalize time to start at 0
        flight_data = df[flight_start:flight_end].copy()
        start_time = flight_data['Time'].iloc[0]
        flight_data['Time'] = flight_data['Time'] - start_time
        time_data = flight_data['Time']
        
        # Calculate velocity (m/s) using central difference
        dt = 0.05  # 50ms sampling rate
        flight_data['Velocity_m_s'] = np.gradient(flight_data['Calibrated_Altitude'], dt)
        
        # Calculate acceleration (m/s²) using central difference of velocity
        flight_data['Acceleration_m_s2'] = np.gradient(flight_data['Velocity_m_s'], dt)
        
        # Smooth acceleration data using rolling average
        window_size = 10  # 500ms window (10 points at 50ms sampling)
        flight_data['Acceleration_m_s2_smooth'] = flight_data['Acceleration_m_s2'].rolling(window=window_size, center=True).mean()
        
        # Create subplots
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
        
        # Find apogee time for vertical line (in flight_data)
        apogee_time = flight_data.loc[flight_data['Calibrated_Altitude'].idxmax(), 'Time']
        
        # Plot 1: Altitude (with dual axis)
        ax1_m = ax1
        ax1_ft = ax1.twinx()  # Create second y-axis
        
        # Plot altitude in meters (blue) and feet (dashed gray)
        ax1_m.plot(time_data, flight_data['Calibrated_Altitude'], 'b-', linewidth=1)
        ax1_ft.plot(time_data, flight_data['Altitude_ft'], 'gray', linestyle='--', alpha=0.5)
        
        # Add vertical line at apogee
        ax1_m.axvline(x=apogee_time, color='r', linestyle='--', alpha=0.5)
        ax1_m.text(apogee_time, ax1_m.get_ylim()[1], f't={apogee_time:.1f}s', 
                  rotation=90, va='top', ha='right')
        
        ax1_m.set_ylabel('Altitude (m)')
        ax1_ft.set_ylabel('Altitude (ft)')
        ax1_m.grid(True)
        ax1_m.set_title('Flight Data Analysis')
        
        # Remove padding from axes
        ax1_m.margins(x=0)
        ax2.margins(x=0)
        ax3.margins(x=0)
        
        # Add altitude statistics
        max_altitude_m = flight_data['Calibrated_Altitude'].max()
        max_altitude_ft = flight_data['Altitude_ft'].max()
        flight_duration = time_data.iloc[-1] - time_data.iloc[0]
        stats_text = f'Max Altitude: {max_altitude_m:.1f} m ({max_altitude_ft:.1f} ft)\nFlight Duration: {flight_duration:.1f} s'
        ax1_m.text(0.98, 0.98, stats_text, transform=ax1_m.transAxes, 
                  verticalalignment='top', horizontalalignment='right',
                  bbox=dict(facecolor='white', alpha=0.8))
        
        # Plot 2: Velocity with apogee line
        ax2.plot(time_data, flight_data['Velocity_m_s'], 'g-', linewidth=1)
        ax2.axvline(x=apogee_time, color='r', linestyle='--', alpha=0.5)
        ax2.set_ylabel('Velocity (m/s)')
        ax2.grid(True)
        
        # Add velocity statistics
        max_velocity = flight_data['Velocity_m_s'].max()
        ax2.text(0.98, 0.98, f'Max Velocity: {max_velocity:.1f} m/s', 
                transform=ax2.transAxes, verticalalignment='top', horizontalalignment='right',
                bbox=dict(facecolor='white', alpha=0.8))
        
        # Plot 3: Acceleration with apogee line
        ax3.plot(time_data, flight_data['Acceleration_m_s2_smooth'], 'r-', linewidth=1)
        ax3.axvline(x=apogee_time, color='r', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Time (seconds)')
        ax3.set_ylabel('Acceleration (m/s²)')
        ax3.grid(True)
        
        # Add acceleration statistics using smoothed data
        max_accel = flight_data['Acceleration_m_s2_smooth'].max()
        ax3.text(0.98, 0.98, f'Max Acceleration: {max_accel:.1f} m/s²', 
                transform=ax3.transAxes, verticalalignment='top', horizontalalignment='right',
                bbox=dict(facecolor='white', alpha=0.8))
        
        # Adjust layout to prevent overlap
        plt.tight_layout()
        
        # Save the plot
        output_file = csv_path.replace('.csv', '_analysis.png')
        plt.savefig(output_file)
        print(f"Plot saved as: {output_file}")
        
        # Print summary statistics
        print(f"Max altitude: {max_altitude_m:.1f} m ({max_altitude_ft:.1f} ft)")
        print(f"Max velocity: {max_velocity:.1f} m/s")
        print(f"Max acceleration: {max_accel:.1f} m/s²")
        print(f"Flight duration: {flight_duration:.1f} s")
        
        sys.exit(0)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python plot_altitude.py data.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    plot_altitude_data(csv_path)
