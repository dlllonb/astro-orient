#ifndef BME280_APP_H
#define BME280_APP_H

#include <stdint.h>

typedef struct
{
    int32_t temperature_c_x100;
    uint32_t pressure_pa_x100;
    uint32_t humidity_percent_x1024;
} BME280_AppData;

uint8_t BME280_App_Init(void);
uint8_t BME280_App_Read(BME280_AppData *data);
uint8_t BME280_App_Address(void);

#endif
