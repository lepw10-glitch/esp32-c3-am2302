#include <Arduino.h>
#include <U8g2lib.h>
#include <DHTesp.h>

U8G2_SSD1306_72X40_ER_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE, 6, 5);

DHTesp dht;
const int DHT_PIN = 4;

void setup()
{
    Serial.begin(115200);

    display.begin();
    display.setContrast(255);
    display.setFont(u8g2_font_6x10_tf);

    dht.setup(DHT_PIN, DHTesp::AM2302);
}

void loop()
{
    TempAndHumidity data = dht.getTempAndHumidity();

    display.clearBuffer();

    if (dht.getStatus() == DHTesp::ERROR_NONE)
    {
        char line[16];

        snprintf(line, sizeof(line), "TEMP %.1f C", data.temperature);
        display.drawStr(0, 12, line);

        snprintf(line, sizeof(line), "HUM  %.1f %%", data.humidity);
        display.drawStr(0, 26, line);

        Serial.printf("T=%.1f H=%.1f\n", data.temperature, data.humidity);
    }
    else
    {
        display.drawStr(0, 12, "Sensor");
        display.drawStr(0, 26, "Fehler");
        Serial.println(dht.getStatusString());
    }

    display.sendBuffer();
    delay(10000);  // AM2302 maximal alle ~10 s auslesen
}