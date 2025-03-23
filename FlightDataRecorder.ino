/**
 * Flight Data Recorder
 * 
 * This program is used to record the altitude data during the flight. It reads the altitude data 
 * from the BMP390 sensor and writes it to the SD card.
 * 
 * When the program starts, it will keep reading the altitude data from the BMP390 sensor and 
 * write a new file to the SD card every 50ms.
 * 
 * The file name will be the current date and time.
 * 
 * The file will be a CSV file with the following columns:
 * - Date and time
 * - Altitude
 * - Pressure
 * - Temperature
 */

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include "Adafruit_BMP3XX.h"
#include "FS.h"
#include "SD_MMC.h"
#include "time.h"
#include <FastLED.h>

// BMP390 sensor configuration
#define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_BMP3XX bmp;

// SD card pins for SDIO interface
const int pin_sdioCLK = 38;
const int pin_sdioCMD = 34;
const int pin_sdioD0 = 39;
const int pin_sdioD1 = 40;
const int pin_sdioD2 = 47;
const int pin_sdioD3 = 33;

// Timing variables
unsigned long lastReadTime = 0;
const unsigned long READ_INTERVAL = 50; // 50ms interval

// Global file name for this session
String dataFileName;
File dataFile;

// Change the prefix to not include the slash
const String FILE_PREFIX = "flight_";  // Remove the leading slash here
const String FILE_EXTENSION = ".csv";

// Add this helper function
String padNumber(int number, int width) {
  String result = String(number);
  while (result.length() < width) {
    result = "0" + result;
  }
  return result;
}

// New function to find the next available file number
int findNextFileNumber() {
  int maxNumber = 0;
  File root = SD_MMC.open("/");
  if (!root) {
    Serial.println("Failed to open root directory");
    return 0;
  }

  Serial.println("Scanning for existing files:");
  File file = root.openNextFile();
  while (file) {
    String fileName = String(file.name());
    Serial.print("Found file: ");
    Serial.println(fileName);
    
    // Check if this is one of our flight files
    if (fileName.startsWith(FILE_PREFIX) && fileName.endsWith(FILE_EXTENSION)) {
      // Extract the number between prefix and extension
      String numberPart = fileName.substring(FILE_PREFIX.length(), 
                                          fileName.length() - FILE_EXTENSION.length());
      Serial.print("Extracted number: ");
      Serial.println(numberPart);
      
      int currentNumber = numberPart.toInt();
      if (currentNumber > maxNumber) {
        maxNumber = currentNumber;
        Serial.print("New max number: ");
        Serial.println(maxNumber);
      }
    }
    file.close();
    file = root.openNextFile();
  }
  
  root.close();
  Serial.print("Next file number will be: ");
  Serial.println(maxNumber + 1);
  return maxNumber + 1;
}

// Add LED definitions after other definitions
#define LED_PIN     46
#define COLOR_ORDER GRB
#define CHIPSET     WS2812
#define NUM_LEDS    1
#define BRIGHTNESS  10

CRGB leds[NUM_LEDS];

void setup() {
  delay(1000);

  Serial.begin(115200);

  // #ifdef USB_SERIAL
  // while (!Serial);
  // #endif

  Serial.println("Flight Data Recorder Starting...");
  
  // Initialize LED first
  FastLED.addLeds<CHIPSET, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS).setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  
  // Set LED to red during initialization
  leds[0] = CRGB::Red;
  FastLED.show();

  // Initialize BMP390 sensor
  if (!bmp.begin_I2C()) {
    Serial.println("Could not find BMP390 sensor! Check wiring.");
    // Keep LED red if sensor fails
    while (1);
  }

  // Configure BMP390 sensor settings
  bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_8X);
  bmp.setPressureOversampling(BMP3_OVERSAMPLING_4X);
  bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_3);
  bmp.setOutputDataRate(BMP3_ODR_50_HZ);

  // Initialize SD card
  if (!SD_MMC.setPins(pin_sdioCLK, pin_sdioCMD, pin_sdioD0, pin_sdioD1, pin_sdioD2, pin_sdioD3)) {
    Serial.println("SD card pin assignment failed!");
    // Keep LED red if SD card fails
    while (1);
  }

  if (!SD_MMC.begin()) {
    Serial.println("SD card initialization failed!");
    // Keep LED red if SD card fails
    while (1);
  }

  // Let voltage settle before file ops
  delay(1000);

  int fileNumber = findNextFileNumber();
  dataFileName = "/" + FILE_PREFIX + padNumber(fileNumber, 5) + FILE_EXTENSION;
  Serial.print("Creating file: ");
  Serial.println(dataFileName);
  
  dataFile = SD_MMC.open(dataFileName, FILE_WRITE);
  if (!dataFile) {
    Serial.println("Failed to create data file!");
    // Keep LED red if file creation fails
    while (1);
  }

  // Write CSV header
  dataFile.println("Timestamp,Altitude(m),Pressure(hPa),Temperature(C)");
  dataFile.flush();
  
  // Everything initialized successfully, set LED to green
  leds[0] = CRGB::Green;
  FastLED.show();
  
  Serial.println("Flight Data Recorder ready!");
  Serial.println("Recording to file: " + dataFileName);
}

String getTimestamp() {
  return String(millis());
}

void recordDataPoint() {
  if (bmp.performReading()) {
    float altitude = bmp.readAltitude(SEALEVELPRESSURE_HPA);
    float pressure = bmp.pressure / 100.0;
    float temperature = bmp.temperature;
    
    // Write data row
    dataFile.print(getTimestamp());
    dataFile.print(",");
    dataFile.print(altitude);
    dataFile.print(",");
    dataFile.print(pressure);
    dataFile.print(",");
    dataFile.println(temperature);
    dataFile.flush();
    
    // Data recorded successfully, ensure LED is green
    leds[0] = CRGB::Green;
    FastLED.show();
  } else {
    Serial.println("Failed to read sensor data");
    // Show error with red LED
    leds[0] = CRGB::Red;
    FastLED.show();
  }
}

void loop() {
  unsigned long currentTime = millis();
  
  // Check if it's time to take a reading
  if (currentTime - lastReadTime >= READ_INTERVAL) {
    recordDataPoint();
    lastReadTime = currentTime;
  }
}