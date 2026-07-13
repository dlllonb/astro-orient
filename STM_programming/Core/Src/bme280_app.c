#include "main.h"
#include "bme280.h"
#include "bme280_app.h"

#define BME280_I2C_TIMING_100KHZ  0x20303E5DU
#define BME280_I2C_TIMEOUT_MS     100U

typedef struct
{
    I2C_HandleTypeDef *bus;
    uint8_t address;
} BME280_I2C_Context;

static I2C_HandleTypeDef hi2c1;
static struct bme280_dev bme_device;
static BME280_I2C_Context bme_context;
static uint8_t bme_ready;

static int8_t bme_i2c_read(uint8_t reg_addr, uint8_t *reg_data, uint32_t length, void *intf_ptr)
{
    BME280_I2C_Context *context = (BME280_I2C_Context *)intf_ptr;
    HAL_StatusTypeDef status;

    status = HAL_I2C_Mem_Read(context->bus,
                              (uint16_t)(context->address << 1U),
                              reg_addr,
                              I2C_MEMADD_SIZE_8BIT,
                              reg_data,
                              (uint16_t)length,
                              BME280_I2C_TIMEOUT_MS);
    return status == HAL_OK ? BME280_OK : BME280_E_COMM_FAIL;
}

static int8_t bme_i2c_write(uint8_t reg_addr, const uint8_t *reg_data, uint32_t length, void *intf_ptr)
{
    BME280_I2C_Context *context = (BME280_I2C_Context *)intf_ptr;
    HAL_StatusTypeDef status;

    status = HAL_I2C_Mem_Write(context->bus,
                               (uint16_t)(context->address << 1U),
                               reg_addr,
                               I2C_MEMADD_SIZE_8BIT,
                               (uint8_t *)reg_data,
                               (uint16_t)length,
                               BME280_I2C_TIMEOUT_MS);
    return status == HAL_OK ? BME280_OK : BME280_E_COMM_FAIL;
}

static void bme_delay_us(uint32_t period_us, void *intf_ptr)
{
    (void)intf_ptr;
    HAL_Delay((period_us + 999U) / 1000U);
}

static uint8_t bme_bus_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_I2C1_CLK_ENABLE();

    /* LQFP48 pin 42 = PB6/SCL, pin 43 = PB7/SDA. */
    gpio.Pin = GPIO_PIN_6 | GPIO_PIN_7;
    gpio.Mode = GPIO_MODE_AF_OD;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF1_I2C1;
    HAL_GPIO_Init(GPIOB, &gpio);

    hi2c1.Instance = I2C1;
    hi2c1.Init.Timing = BME280_I2C_TIMING_100KHZ;
    hi2c1.Init.OwnAddress1 = 0;
    hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c1.Init.OwnAddress2 = 0;
    hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;

    if (HAL_I2C_Init(&hi2c1) != HAL_OK)
    {
        return 0U;
    }

    if (HAL_I2CEx_ConfigAnalogFilter(&hi2c1, I2C_ANALOGFILTER_ENABLE) != HAL_OK)
    {
        return 0U;
    }

    return 1U;
}

uint8_t BME280_App_Init(void)
{
    struct bme280_settings settings = {0};
    int8_t result;
    const uint8_t addresses[] = {0x77U, 0x76U};
    uint32_t index;

    bme_ready = 0U;
    if (bme_bus_init() == 0U)
    {
        return 0U;
    }

    bme_context.bus = &hi2c1;
    bme_device.intf = BME280_I2C_INTF;
    bme_device.intf_ptr = &bme_context;
    bme_device.read = bme_i2c_read;
    bme_device.write = bme_i2c_write;
    bme_device.delay_us = bme_delay_us;

    result = BME280_E_COMM_FAIL;
    for (index = 0; index < (sizeof(addresses) / sizeof(addresses[0])); index++)
    {
        bme_context.address = addresses[index];
        result = bme280_init(&bme_device);
        if (result == BME280_OK)
        {
            break;
        }
    }

    if (result != BME280_OK)
    {
        return 0U;
    }

    settings.osr_h = BME280_OVERSAMPLING_1X;
    settings.osr_p = BME280_OVERSAMPLING_4X;
    settings.osr_t = BME280_OVERSAMPLING_2X;
    settings.filter = BME280_FILTER_COEFF_4;
    settings.standby_time = BME280_STANDBY_TIME_500_MS;

    result = bme280_set_sensor_settings(BME280_SEL_ALL_SETTINGS, &settings, &bme_device);
    if (result == BME280_OK)
    {
        result = bme280_set_sensor_mode(BME280_POWERMODE_NORMAL, &bme_device);
    }

    bme_ready = result == BME280_OK ? 1U : 0U;
    return bme_ready;
}

uint8_t BME280_App_Read(BME280_AppData *data)
{
    struct bme280_data measurement;

    if ((data == NULL) || (bme_ready == 0U))
    {
        return 0U;
    }

    if (bme280_get_sensor_data(BME280_ALL, &measurement, &bme_device) != BME280_OK)
    {
        return 0U;
    }

    data->temperature_c_x100 = measurement.temperature;
    data->pressure_pa_x100 = measurement.pressure;
    data->humidity_percent_x1024 = measurement.humidity;
    return 1U;
}

uint8_t BME280_App_Address(void)
{
    return bme_ready != 0U ? bme_context.address : 0U;
}
