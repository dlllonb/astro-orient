/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "bme280_app.h"
#include "usb_device.h"
#include "usbd_cdc_if.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
typedef enum
{
    NEOPIXEL_D1 = 1,
    NEOPIXEL_D2 = 2,
    NEOPIXEL_D3 = 3
} NeopixelId;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define PHOTO_SAMPLE_COUNT 32U
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
static uint8_t bme_available;
static uint8_t photo_available;
static uint8_t stream_enabled = 1U;
static uint32_t stream_interval_ms = 500U;
static uint32_t next_stream_ms;
static char command_buffer[64];
static uint32_t command_length;
static ADC_HandleTypeDef hadc;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

#define NEOPIXEL_ZERO_TICKS     14U  /* 0.292 us at 48 MHz */
#define NEOPIXEL_ONE_TICKS      36U  /* 0.750 us at 48 MHz */
#define NEOPIXEL_RESET_SLOTS   200U  /* 250 us low */
#define NEOPIXEL_DATA_SLOTS     24U
#define NEOPIXEL_TOTAL_SLOTS   (NEOPIXEL_DATA_SLOTS + NEOPIXEL_RESET_SLOTS)

static uint16_t neopixel_pwm[NEOPIXEL_TOTAL_SLOTS];

/* D1=PB1/TIM3_CH4, D2=PB0/TIM3_CH3, D3=PA6/TIM3_CH1, all AF1. */
static void neopixel_timer_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    if (HAL_RCC_GetPCLK1Freq() != 48000000U)
    {
        Error_Handler();
    }

    __HAL_RCC_DMA1_CLK_ENABLE();
    __HAL_RCC_TIM3_CLK_ENABLE();

    TIM3->CR1 = 0;
    TIM3->PSC = 0;
    TIM3->ARR = 59U;       /* 48 MHz / 60 = 800 kHz */
    TIM3->CCR1 = 0;
    TIM3->CCR3 = 0;
    TIM3->CCR4 = 0;
    TIM3->CCMR1 = (6U << TIM_CCMR1_OC1M_Pos) | TIM_CCMR1_OC1PE;
    TIM3->CCMR2 = (6U << TIM_CCMR2_OC3M_Pos) | TIM_CCMR2_OC3PE |
                   (6U << TIM_CCMR2_OC4M_Pos) | TIM_CCMR2_OC4PE;
    TIM3->CCER = TIM_CCER_CC1E | TIM_CCER_CC3E | TIM_CCER_CC4E;
    TIM3->CR1 = TIM_CR1_ARPE;
    TIM3->EGR = TIM_EGR_UG;
    TIM3->SR = 0;

    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF1_TIM3;
    HAL_GPIO_Init(GPIOB, &gpio);

    gpio.Pin = GPIO_PIN_6;
    HAL_GPIO_Init(GPIOA, &gpio);
}

static void neopixel_encode_byte(uint8_t byte_value, uint32_t *slot)
{
    for (int32_t bit = 7; bit >= 0; bit--)
    {
        neopixel_pwm[*slot] = ((byte_value >> bit) & 1U) != 0U
                            ? NEOPIXEL_ONE_TICKS
                            : NEOPIXEL_ZERO_TICKS;
        (*slot)++;
    }
}

static void neopixel_send_color(NeopixelId led, uint8_t red, uint8_t green, uint8_t blue)
{
    uint32_t slot = 0;
    uint32_t transfer_start;
    volatile uint32_t *compare_register;

    switch (led)
    {
        case NEOPIXEL_D1:
            compare_register = &TIM3->CCR4;
            break;
        case NEOPIXEL_D2:
            compare_register = &TIM3->CCR3;
            break;
        case NEOPIXEL_D3:
            compare_register = &TIM3->CCR1;
            break;
        default:
            return;
    }

    /* SKC6812RV wire order is GRB, most-significant bit first. */
    neopixel_encode_byte(green, &slot);
    neopixel_encode_byte(red, &slot);
    neopixel_encode_byte(blue, &slot);

    while (slot < NEOPIXEL_TOTAL_SLOTS)
    {
        neopixel_pwm[slot++] = 0;
    }

    TIM3->CR1 &= ~TIM_CR1_CEN;
    TIM3->DIER &= ~TIM_DIER_UDE;
    DMA1_Channel3->CCR &= ~DMA_CCR_EN;
    DMA1->IFCR = DMA_IFCR_CGIF3;

    TIM3->CNT = 0;
    TIM3->CCR1 = 0;
    TIM3->CCR3 = 0;
    TIM3->CCR4 = 0;
    TIM3->EGR = TIM_EGR_UG;
    TIM3->SR = 0;

    DMA1_Channel3->CPAR = (uint32_t)compare_register;
    DMA1_Channel3->CMAR = (uint32_t)neopixel_pwm;
    DMA1_Channel3->CNDTR = NEOPIXEL_TOTAL_SLOTS;
    DMA1_Channel3->CCR = DMA_CCR_DIR | DMA_CCR_MINC |
                         DMA_CCR_PSIZE_0 | DMA_CCR_MSIZE_0 | DMA_CCR_PL_1;

    TIM3->DIER |= TIM_DIER_UDE;
    DMA1_Channel3->CCR |= DMA_CCR_EN;
    TIM3->CR1 |= TIM_CR1_CEN;

    transfer_start = HAL_GetTick();
    while ((DMA1->ISR & DMA_ISR_TCIF3) == 0U)
    {
        if ((HAL_GetTick() - transfer_start) > 10U)
        {
            Error_Handler();
        }
    }

    DMA1_Channel3->CCR &= ~DMA_CCR_EN;
    TIM3->DIER &= ~TIM_DIER_UDE;
    *compare_register = 0;

    /* Extra margin beyond the 200 us reset already present in the buffer. */
    HAL_Delay(1);
}

static void neopixel_off(NeopixelId led)
{
    neopixel_send_color(led, 0U, 0U, 0U);
}

static uint8_t photoresistor_init(void)
{
    GPIO_InitTypeDef gpio = {0};
    uint32_t start;

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_HSI14_ENABLE();

    start = HAL_GetTick();
    while (__HAL_RCC_GET_FLAG(RCC_FLAG_HSI14RDY) == RESET)
    {
        if ((HAL_GetTick() - start) > 10U)
        {
            return 0U;
        }
    }

    gpio.Pin = GPIO_PIN_1 | GPIO_PIN_4;
    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    hadc.Instance = ADC1;
    hadc.Init.ClockPrescaler = ADC_CLOCK_ASYNC_DIV1;
    hadc.Init.Resolution = ADC_RESOLUTION_12B;
    hadc.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc.Init.ScanConvMode = ADC_SCAN_DIRECTION_FORWARD;
    hadc.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
    hadc.Init.LowPowerAutoWait = DISABLE;
    hadc.Init.LowPowerAutoPowerOff = DISABLE;
    hadc.Init.ContinuousConvMode = DISABLE;
    hadc.Init.DiscontinuousConvMode = DISABLE;
    hadc.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc.Init.DMAContinuousRequests = DISABLE;
    hadc.Init.Overrun = ADC_OVR_DATA_PRESERVED;
    hadc.Init.SamplingTimeCommon = ADC_SAMPLETIME_239CYCLES_5;

    if (HAL_ADC_Init(&hadc) != HAL_OK)
    {
        return 0U;
    }

    return HAL_ADCEx_Calibration_Start(&hadc) == HAL_OK ? 1U : 0U;
}

static uint8_t photoresistor_read_channel(uint32_t channel, uint16_t *result)
{
    if (result == NULL)
    {
        return 0U;
    }

    ADC1->CHSELR = channel;
    if (HAL_ADC_Start(&hadc) != HAL_OK)
    {
        return 0U;
    }
    if (HAL_ADC_PollForConversion(&hadc, 5U) != HAL_OK)
    {
        (void)HAL_ADC_Stop(&hadc);
        return 0U;
    }

    *result = (uint16_t)HAL_ADC_GetValue(&hadc);
    return HAL_ADC_Stop(&hadc) == HAL_OK ? 1U : 0U;
}

static uint8_t photoresistor_read_averages(uint16_t *light_1, uint16_t *light_2)
{
    uint32_t sum_1 = 0U;
    uint32_t sum_2 = 0U;
    uint32_t index;
    uint16_t sample_1;
    uint16_t sample_2;

    if ((light_1 == NULL) || (light_2 == NULL) || (photo_available == 0U))
    {
        return 0U;
    }

    for (index = 0U; index < PHOTO_SAMPLE_COUNT; index++)
    {
        if ((photoresistor_read_channel(ADC_CHANNEL_1, &sample_1) == 0U) ||
            (photoresistor_read_channel(ADC_CHANNEL_4, &sample_2) == 0U))
        {
            return 0U;
        }
        sum_1 += sample_1;
        sum_2 += sample_2;
    }

    *light_1 = (uint16_t)((sum_1 + (PHOTO_SAMPLE_COUNT / 2U)) / PHOTO_SAMPLE_COUNT);
    *light_2 = (uint16_t)((sum_2 + (PHOTO_SAMPLE_COUNT / 2U)) / PHOTO_SAMPLE_COUNT);
    return 1U;
}

static uint8_t time_reached(uint32_t now, uint32_t deadline)
{
    return (int32_t)(now - deadline) >= 0 ? 1U : 0U;
}

static void usb_send_status(void)
{
    char message[224];

    if (bme_available != 0U)
    {
        (void)snprintf(message, sizeof(message),
                       "{\"type\":\"status\",\"device\":\"astro_orient\","
                       "\"bme280\":true,\"i2c_address\":\"0x%02X\","
                       "\"photoresistors\":%s,"
                       "\"stream_interval_ms\":%lu}\r\n",
                       BME280_App_Address(),
                       photo_available != 0U ? "true" : "false",
                       (unsigned long)stream_interval_ms);
    }
    else
    {
        (void)snprintf(message, sizeof(message),
                       "{\"type\":\"status\",\"device\":\"astro_orient\","
                       "\"bme280\":false,\"photoresistors\":%s,"
                       "\"stream_interval_ms\":%lu}\r\n",
                       photo_available != 0U ? "true" : "false",
                       (unsigned long)stream_interval_ms);
    }

    (void)AstroCDC_Write(message);
}

static void usb_send_measurement(void)
{
    BME280_AppData data;
    char message[384];
    uint32_t absolute_temperature;
    uint32_t pressure_integer;
    uint32_t pressure_fraction;
    uint32_t humidity_integer;
    uint32_t humidity_fraction;
    uint16_t light_1 = 0U;
    uint16_t light_2 = 0U;
    uint16_t ambient_light;
    uint32_t ambient_percent_x100;
    uint8_t bme_ok;
    uint8_t photo_ok;
    const char *temperature_sign;

    bme_ok = ((bme_available != 0U) && (BME280_App_Read(&data) != 0U)) ? 1U : 0U;
    photo_ok = photoresistor_read_averages(&light_1, &light_2);
    ambient_light = (uint16_t)(((uint32_t)light_1 + (uint32_t)light_2 + 1U) / 2U);
    ambient_percent_x100 = ((uint32_t)ambient_light * 10000U + 2047U) / 4095U;

    if (bme_ok == 0U)
    {
        (void)snprintf(message, sizeof(message),
                       "{\"type\":\"environment\",\"timestamp_ms\":%lu,"
                       "\"bme280_ok\":false,\"temperature_c\":null,"
                       "\"pressure_hpa\":null,\"humidity_percent\":null,"
                       "\"photoresistors_ok\":%s,\"light_1_raw_avg\":%u,"
                       "\"light_2_raw_avg\":%u,\"ambient_light_raw_avg\":%u,"
                       "\"ambient_light_percent\":%lu.%02lu}\r\n",
                       (unsigned long)HAL_GetTick(),
                       photo_ok != 0U ? "true" : "false",
                       light_1, light_2, ambient_light,
                       (unsigned long)(ambient_percent_x100 / 100U),
                       (unsigned long)(ambient_percent_x100 % 100U));
        (void)AstroCDC_Write(message);
        return;
    }

    temperature_sign = data.temperature_c_x100 < 0 ? "-" : "";
    absolute_temperature = data.temperature_c_x100 < 0
                         ? (uint32_t)(-(int64_t)data.temperature_c_x100)
                         : (uint32_t)data.temperature_c_x100;
    pressure_integer = data.pressure_pa_x100 / 10000U;
    pressure_fraction = (data.pressure_pa_x100 % 10000U) / 100U;
    humidity_integer = data.humidity_percent_x1024 / 1024U;
    humidity_fraction = ((data.humidity_percent_x1024 % 1024U) * 100U) / 1024U;

    (void)snprintf(message, sizeof(message),
                   "{\"type\":\"environment\",\"timestamp_ms\":%lu,"
                   "\"bme280_ok\":true,"
                   "\"temperature_c\":%s%lu.%02lu,\"pressure_hpa\":%lu.%02lu,"
                   "\"humidity_percent\":%lu.%02lu,\"photoresistors_ok\":%s,"
                   "\"light_1_raw_avg\":%u,\"light_2_raw_avg\":%u,"
                   "\"ambient_light_raw_avg\":%u,"
                   "\"ambient_light_percent\":%lu.%02lu}\r\n",
                   (unsigned long)HAL_GetTick(),
                   temperature_sign,
                   (unsigned long)(absolute_temperature / 100U),
                   (unsigned long)(absolute_temperature % 100U),
                   (unsigned long)pressure_integer,
                   (unsigned long)pressure_fraction,
                   (unsigned long)humidity_integer,
                   (unsigned long)humidity_fraction,
                   photo_ok != 0U ? "true" : "false",
                   light_1, light_2, ambient_light,
                   (unsigned long)(ambient_percent_x100 / 100U),
                   (unsigned long)(ambient_percent_x100 % 100U));
    (void)AstroCDC_Write(message);
}

static void usb_send_response(const char *command, uint8_t ok, const char *details)
{
    char message[384];

    (void)snprintf(message, sizeof(message),
                   "{\"type\":\"response\",\"command\":\"%s\","
                   "\"ok\":%s%s%s}\r\n",
                   command,
                   ok != 0U ? "true" : "false",
                   (details != NULL) && (details[0] != '\0') ? "," : "",
                   (details != NULL) ? details : "");
    (void)AstroCDC_Write(message);
}

static void set_named_led(NeopixelId led, uint8_t red, uint8_t green, uint8_t blue,
                          const char *command_name)
{
    char detail[96];

    neopixel_send_color(led, red, green, blue);
    (void)snprintf(detail, sizeof(detail),
                   "\"led\":\"D%u\",\"red\":%u,\"green\":%u,\"blue\":%u",
                   (unsigned int)led, red, green, blue);
    usb_send_response(command_name, 1U, detail);
}

static void process_led_command(const char *command)
{
    NeopixelId led;
    const char *cursor;
    char *end;
    unsigned long red;
    unsigned long green;
    unsigned long blue;

    if ((command[5] != '2') && (command[5] != '3'))
    {
        usb_send_response("LED", 0U, "\"message\":\"only_D2_and_D3_are_host_controlled\"");
        return;
    }
    led = command[5] == '2' ? NEOPIXEL_D2 : NEOPIXEL_D3;

    if (strcmp(&command[7], "OFF") == 0)
    {
        set_named_led(led, 0U, 0U, 0U, "LED");
    }
    else if (strcmp(&command[7], "YELLOW") == 0)
    {
        set_named_led(led, 12U, 8U, 0U, "LED");
    }
    else if (strcmp(&command[7], "GREEN") == 0)
    {
        set_named_led(led, 0U, 12U, 0U, "LED");
    }
    else if (strcmp(&command[7], "RED") == 0)
    {
        set_named_led(led, 12U, 0U, 0U, "LED");
    }
    else if (strncmp(&command[7], "RGB ", 4U) == 0)
    {
        cursor = &command[11];
        red = strtoul(cursor, &end, 10);
        if ((end == cursor) || (*end != ' '))
        {
            usb_send_response("LED", 0U, "\"message\":\"use_LED_D2_RGB_r_g_b\"");
            return;
        }
        cursor = end + 1;
        green = strtoul(cursor, &end, 10);
        if ((end == cursor) || (*end != ' '))
        {
            usb_send_response("LED", 0U, "\"message\":\"use_LED_D2_RGB_r_g_b\"");
            return;
        }
        cursor = end + 1;
        blue = strtoul(cursor, &end, 10);
        if ((end == cursor) || (*end != '\0') ||
            (red > 255UL) || (green > 255UL) || (blue > 255UL))
        {
            usb_send_response("LED", 0U, "\"message\":\"RGB_values_must_be_0_to_255\"");
            return;
        }
        set_named_led(led, (uint8_t)red, (uint8_t)green, (uint8_t)blue, "LED");
    }
    else
    {
        usb_send_response("LED", 0U,
                          "\"message\":\"use_OFF_RED_YELLOW_GREEN_or_RGB_r_g_b\"");
    }
}

static void process_command(char *command)
{
    char *end;
    unsigned long requested_rate;
    uint32_t index;

    for (index = 0U; command[index] != '\0'; index++)
    {
        if ((command[index] >= 'a') && (command[index] <= 'z'))
        {
            command[index] = (char)(command[index] - ('a' - 'A'));
        }
    }

    if (strcmp(command, "PING") == 0)
    {
        usb_send_status();
    }
    else if (strcmp(command, "READ") == 0)
    {
        usb_send_measurement();
    }
    else if (strcmp(command, "STREAM ON") == 0)
    {
        stream_enabled = 1U;
        next_stream_ms = HAL_GetTick();
        usb_send_response("STREAM", 1U, "\"enabled\":true");
    }
    else if (strcmp(command, "STREAM OFF") == 0)
    {
        stream_enabled = 0U;
        usb_send_response("STREAM", 1U, "\"enabled\":false");
    }
    else if (strcmp(command, "GPS OFF") == 0)
    {
        set_named_led(NEOPIXEL_D2, 12U, 0U, 0U, "GPS");
    }
    else if ((strcmp(command, "GPS CONNECTED") == 0) ||
             (strcmp(command, "GPS SEARCHING") == 0))
    {
        set_named_led(NEOPIXEL_D2, 12U, 8U, 0U, "GPS");
    }
    else if (strcmp(command, "GPS LOCKED") == 0)
    {
        set_named_led(NEOPIXEL_D2, 0U, 12U, 0U, "GPS");
    }
    else if (strcmp(command, "IMU OFF") == 0)
    {
        set_named_led(NEOPIXEL_D3, 12U, 0U, 0U, "IMU");
    }
    else if (strcmp(command, "IMU CONNECTED") == 0)
    {
        set_named_led(NEOPIXEL_D3, 12U, 8U, 0U, "IMU");
    }
    else if (strcmp(command, "IMU READY") == 0)
    {
        set_named_led(NEOPIXEL_D3, 0U, 12U, 0U, "IMU");
    }
    else if ((strlen(command) >= 8U) &&
             (strncmp(command, "LED D", 5U) == 0) && (command[6] == ' '))
    {
        process_led_command(command);
    }
    else if (strncmp(command, "RATE ", 5U) == 0)
    {
        end = NULL;
        requested_rate = strtoul(&command[5], &end, 10);
        if ((end == &command[5]) || (*end != '\0') ||
            (requested_rate < 100UL) || (requested_rate > 60000UL))
        {
            usb_send_response("RATE", 0U,
                              "\"message\":\"rate_must_be_100_to_60000_ms\"");
        }
        else
        {
            char detail[64];
            stream_interval_ms = (uint32_t)requested_rate;
            next_stream_ms = HAL_GetTick() + stream_interval_ms;
            (void)snprintf(detail, sizeof(detail),
                           "\"stream_interval_ms\":%lu",
                           (unsigned long)stream_interval_ms);
            usb_send_response("RATE", 1U, detail);
        }
    }
    else if (strcmp(command, "HELP") == 0)
    {
        usb_send_response("HELP", 1U,
                          "\"commands\":[\"PING\",\"READ\",\"STREAM ON\","
                          "\"STREAM OFF\",\"RATE 500\",\"GPS OFF/SEARCHING/LOCKED\","
                          "\"IMU OFF/CONNECTED/READY\",\"LED D2 RGB r g b\",\"HELP\"]");
    }
    else if (command[0] != '\0')
    {
        usb_send_response("UNKNOWN", 0U, "\"message\":\"unknown_command\"");
    }
}

static void process_usb_input(void)
{
    uint8_t value;

    while (AstroCDC_ReadByte(&value) != 0U)
    {
        if (value == '\r')
        {
            continue;
        }

        if (value == '\n')
        {
            command_buffer[command_length] = '\0';
            process_command(command_buffer);
            command_length = 0U;
        }
        else if (command_length < (sizeof(command_buffer) - 1U))
        {
            command_buffer[command_length++] = (char)value;
        }
        else
        {
            command_length = 0U;
            usb_send_response("INPUT", 0U, "\"message\":\"command_too_long\"");
        }
    }
}



/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  /* USER CODE BEGIN 2 */

  /* All three smart LEDs must see a low reset before their first frame. */
  HAL_Delay(1);
  neopixel_timer_init();
  neopixel_off(NEOPIXEL_D1);
  neopixel_off(NEOPIXEL_D2);
  neopixel_off(NEOPIXEL_D3);

  /* D1 is the application-running power indicator and is intentionally dim. */
  neopixel_send_color(NEOPIXEL_D1, 6U, 0U, 0U);
  /* Until the laptop reports otherwise, GPS and IMU are disconnected. */
  neopixel_send_color(NEOPIXEL_D2, 12U, 0U, 0U);
  neopixel_send_color(NEOPIXEL_D3, 12U, 0U, 0U);

  bme_available = BME280_App_Init();
  photo_available = photoresistor_init();
  MX_USB_DEVICE_Init();
  next_stream_ms = HAL_GetTick() + stream_interval_ms;

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    uint32_t now = HAL_GetTick();

    process_usb_input();

    if ((stream_enabled != 0U) && (time_reached(now, next_stream_ms) != 0U))
    {
        next_stream_ms = now + stream_interval_ms;
        usb_send_measurement();
    }

  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInitStruct = {0};
  RCC_CRSInitTypeDef RCC_CRSInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI48;
  RCC_OscInitStruct.HSI48State = RCC_HSI48_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI48;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }

  PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_USB;
  PeriphClkInitStruct.UsbClockSelection = RCC_USBCLKSOURCE_HSI48;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  __HAL_RCC_CRS_CLK_ENABLE();
  RCC_CRSInitStruct.Prescaler = RCC_CRS_SYNC_DIV1;
  RCC_CRSInitStruct.Source = RCC_CRS_SYNC_SOURCE_USB;
  RCC_CRSInitStruct.Polarity = RCC_CRS_SYNC_POLARITY_RISING;
  RCC_CRSInitStruct.ReloadValue = RCC_CRS_RELOADVALUE_DEFAULT;
  RCC_CRSInitStruct.ErrorLimitValue = RCC_CRS_ERRORLIMIT_DEFAULT;
  RCC_CRSInitStruct.HSI48CalibrationValue = RCC_CRS_HSI48CALIBRATION_DEFAULT;
  HAL_RCCEx_CRSConfig(&RCC_CRSInitStruct);
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOF_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_1, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_6, GPIO_PIN_RESET);

  /*Configure GPIO pin : LED1_DATA_Pin */
  GPIO_InitStruct.Pin = GPIO_PIN_0 | GPIO_PIN_1;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  GPIO_InitStruct.Pin = GPIO_PIN_6;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
