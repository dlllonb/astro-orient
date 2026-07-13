#include "main.h"
#include "usb_device.h"
#include "usbd_cdc_if.h"

#include <string.h>

#define CDC_RX_PACKET_SIZE  64U
#define CDC_RX_RING_SIZE   256U
#define CDC_TX_BUFFER_SIZE 512U

static uint8_t usb_rx_packet[CDC_RX_PACKET_SIZE];
static uint8_t usb_rx_ring[CDC_RX_RING_SIZE];
static uint8_t usb_tx_buffer[CDC_TX_BUFFER_SIZE];
static volatile uint16_t usb_rx_head;
static volatile uint16_t usb_rx_tail;

static USBD_CDC_LineCodingTypeDef line_coding =
{
    115200U,
    0x00U,
    0x00U,
    0x08U
};

static int8_t CDC_Itf_Init(void);
static int8_t CDC_Itf_DeInit(void);
static int8_t CDC_Itf_Control(uint8_t cmd, uint8_t *buffer, uint16_t length);
static int8_t CDC_Itf_Receive(uint8_t *buffer, uint32_t *length);

USBD_CDC_ItfTypeDef USBD_CDC_fops =
{
    CDC_Itf_Init,
    CDC_Itf_DeInit,
    CDC_Itf_Control,
    CDC_Itf_Receive
};

static int8_t CDC_Itf_Init(void)
{
    usb_rx_head = 0;
    usb_rx_tail = 0;
    USBD_CDC_SetTxBuffer(&hUsbDeviceFS, usb_tx_buffer, 0);
    USBD_CDC_SetRxBuffer(&hUsbDeviceFS, usb_rx_packet);
    return USBD_OK;
}

static int8_t CDC_Itf_DeInit(void)
{
    return USBD_OK;
}

static int8_t CDC_Itf_Control(uint8_t cmd, uint8_t *buffer, uint16_t length)
{
    (void)length;

    switch (cmd)
    {
        case CDC_SET_LINE_CODING:
            line_coding.bitrate = (uint32_t)buffer[0] |
                                  ((uint32_t)buffer[1] << 8U) |
                                  ((uint32_t)buffer[2] << 16U) |
                                  ((uint32_t)buffer[3] << 24U);
            line_coding.format = buffer[4];
            line_coding.paritytype = buffer[5];
            line_coding.datatype = buffer[6];
            break;

        case CDC_GET_LINE_CODING:
            buffer[0] = (uint8_t)line_coding.bitrate;
            buffer[1] = (uint8_t)(line_coding.bitrate >> 8U);
            buffer[2] = (uint8_t)(line_coding.bitrate >> 16U);
            buffer[3] = (uint8_t)(line_coding.bitrate >> 24U);
            buffer[4] = line_coding.format;
            buffer[5] = line_coding.paritytype;
            buffer[6] = line_coding.datatype;
            break;

        default:
            break;
    }

    return USBD_OK;
}

static int8_t CDC_Itf_Receive(uint8_t *buffer, uint32_t *length)
{
    uint32_t index;

    for (index = 0; index < *length; index++)
    {
        uint16_t next = (uint16_t)((usb_rx_head + 1U) % CDC_RX_RING_SIZE);
        if (next != usb_rx_tail)
        {
            usb_rx_ring[usb_rx_head] = buffer[index];
            usb_rx_head = next;
        }
    }

    USBD_CDC_SetRxBuffer(&hUsbDeviceFS, usb_rx_packet);
    USBD_CDC_ReceivePacket(&hUsbDeviceFS);
    return USBD_OK;
}

uint8_t AstroCDC_ReadByte(uint8_t *value)
{
    uint32_t primask;

    if ((value == NULL) || (usb_rx_tail == usb_rx_head))
    {
        return 0U;
    }

    primask = __get_PRIMASK();
    __disable_irq();
    *value = usb_rx_ring[usb_rx_tail];
    usb_rx_tail = (uint16_t)((usb_rx_tail + 1U) % CDC_RX_RING_SIZE);
    if (primask == 0U)
    {
        __enable_irq();
    }

    return 1U;
}

uint8_t AstroCDC_WriteBytes(const uint8_t *data, uint16_t length)
{
    USBD_CDC_HandleTypeDef *cdc;
    uint32_t start;

    if ((data == NULL) || (length == 0U) || (length > CDC_TX_BUFFER_SIZE))
    {
        return USBD_FAIL;
    }

    if ((hUsbDeviceFS.dev_state != USBD_STATE_CONFIGURED) ||
        (hUsbDeviceFS.pClassData == NULL))
    {
        return USBD_FAIL;
    }

    cdc = (USBD_CDC_HandleTypeDef *)hUsbDeviceFS.pClassData;
    start = HAL_GetTick();
    while (cdc->TxState != 0U)
    {
        if ((HAL_GetTick() - start) > 25U)
        {
            return USBD_BUSY;
        }
    }

    memcpy(usb_tx_buffer, data, length);
    USBD_CDC_SetTxBuffer(&hUsbDeviceFS, usb_tx_buffer, length);
    return USBD_CDC_TransmitPacket(&hUsbDeviceFS);
}

uint8_t AstroCDC_Write(const char *text)
{
    size_t length;

    if (text == NULL)
    {
        return USBD_FAIL;
    }

    length = strlen(text);
    if (length > UINT16_MAX)
    {
        return USBD_FAIL;
    }

    return AstroCDC_WriteBytes((const uint8_t *)text, (uint16_t)length);
}
