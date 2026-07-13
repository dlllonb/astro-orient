#ifndef USBD_CDC_IF_H
#define USBD_CDC_IF_H

#include "usbd_cdc.h"

extern USBD_CDC_ItfTypeDef USBD_CDC_fops;

uint8_t AstroCDC_ReadByte(uint8_t *value);
uint8_t AstroCDC_Write(const char *text);
uint8_t AstroCDC_WriteBytes(const uint8_t *data, uint16_t length);

#endif
