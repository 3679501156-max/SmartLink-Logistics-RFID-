#ifndef	__UART1_H_
	#define __UART1_H_


#define Baudrate1		9600UL				    //定义串口波特率频率									
#define BRT_Reload1	   (256 - MAIN_Fosc / 16 / Baudrate1)	//装入定时器1工作在1倍模式下的益出数



/************函数声明*****************/
void Uart1_Init(void);
void Timer1_Init(void);
//void Uart1_TxByte(unsigned char dat);
//void Uart1_TxString(unsigned char *puts);
//void Uart1_Senddata(unsigned char *DATA,unsigned char length);


#endif




