#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_IS31FL3731.h>

Adafruit_IS31FL3731_Wing ledmatrix = Adafruit_IS31FL3731_Wing();

bool ledState = false;  
unsigned long previousMillis = 0;
int pulseRate = 0, onTime = 0, offTime = 0;
bool isPulsing = false;
int sensorPin = A0;  
int sensorValue = 0;
int currentLux = 100;  

// Initialize the LED matrix and serial communication
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
  Serial.println("Arduino ready to receive commands");

  if (!ledmatrix.begin()) {
    Serial.println("IS31 not found");
    while (1);
  }
  Serial.println("IS31 found!");
}

// Main loop that handles checking serial commands and controlling the LEDs
void loop() {
  checkSerialCommands();  

  if (isPulsing) {
    handlePulsing();  
  } else {
    if (ledState) {
      turnOnLEDs(currentLux);
    } else {
      turnOffLEDs();
    }
  }
  readSensorData(); 
}

// Check if any serial commands are received and process them
void checkSerialCommands() {
  if (Serial.available() > 0) {  
    String command = Serial.readStringUntil('\n');
    command.trim();

    Serial.print("Received Command: ");
    Serial.println(command);

    isPulsing = false;
    ledState = false;

    if (command.startsWith("ON")) {
      parseOnCommand(command);
      ledState = true;
    } 
    else if (command.startsWith("OFF")) {
      ledState = false;
    } 
    else if (command.startsWith("PULSING")) {
      parsePulsingCommand(command);
    } 
    else if (command.startsWith("ADV_PULSING")) {
      parseAdvancedPulsingCommand(command);
    }
    else {
      Serial.println("Invalid Command");
    }
  }
}

// Parse the "ON" command to set the LED brightness and duration
void parseOnCommand(String command) {
  // Format: "ON duration lux"
  int firstSpace = command.indexOf(' ');
  int secondSpace = command.indexOf(' ', firstSpace + 1);
  if (secondSpace > 0) {
    currentLux = command.substring(secondSpace + 1).toInt();
  } else {
    currentLux = 100;  // default
  }
}

// Parse the "PULSING" command to set the pulsing duration, frequency, and brightness
void parsePulsingCommand(String command) {
  // Format: "PULSING duration frequency lux"
  int firstSpace = command.indexOf(' ');
  int secondSpace = command.indexOf(' ', firstSpace + 1);
  int thirdSpace = command.indexOf(' ', secondSpace + 1);

  pulseRate = command.substring(secondSpace + 1, thirdSpace).toInt();
  currentLux = command.substring(thirdSpace + 1).toInt();

  onTime = 1000 / pulseRate / 2;
  offTime = onTime;

  isPulsing = true;
  ledState = false;
}

// Parse the "ADV_PULSING" command to set the advanced pulsing parameters
void parseAdvancedPulsingCommand(String command) {
  // Format: "ADV_PULSING duration onTime offTime lux"
  int firstSpace = command.indexOf(' ');
  int secondSpace = command.indexOf(' ', firstSpace + 1);
  int thirdSpace = command.indexOf(' ', secondSpace + 1);
  int fourthSpace = command.indexOf(' ', thirdSpace + 1);

  onTime = command.substring(secondSpace + 1, thirdSpace).toInt();
  offTime = command.substring(thirdSpace + 1, fourthSpace).toInt();
  currentLux = command.substring(fourthSpace + 1).toInt();

  isPulsing = true;
  ledState = false;
}

// Turn on the LEDs with the specified brightness
void turnOnLEDs(int brightness) {
  brightness = constrain(brightness, 0, 100);  
  for (int x = 0; x < 16; x++) {
    for (int y = 0; y < 9; y++) {
      ledmatrix.drawPixel(x, y, brightness);
    }
  }
}

// Turn off all LEDs
void turnOffLEDs() {
  for (int x = 0; x < 16; x++) {
    for (int y = 0; y < 9; y++) {
      ledmatrix.drawPixel(x, y, 0);
    }
  }
}

// Handle the pulsing effect of the LEDs based on timing
void handlePulsing() {
  unsigned long currentMillis = millis();

  if (Serial.available() > 0) {
    checkSerialCommands();
    return;
  }

  if (ledState) {
    if (currentMillis - previousMillis >= onTime) {
      previousMillis = currentMillis;
      ledState = false;
      turnOffLEDs();
    }
  } else {
    if (currentMillis - previousMillis >= offTime) {
      previousMillis = currentMillis;
      ledState = true;
      turnOnLEDs(currentLux);
    }
  }
}

// Read the sensor data (e.g., light sensor) and print it to serial monitor
void readSensorData() {
  sensorValue = analogRead(sensorPin);  
  Serial.println(sensorValue);
  delay(100);
}
