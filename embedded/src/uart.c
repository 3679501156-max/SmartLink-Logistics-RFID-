#include <STC12C5A60S2.h>
#include "uart1.h"



bit	B_TI;				    //定义B_TI为bit类型
//extern unsigned char xdata RXBuffer1[128];
//unsigned char idata RXBuffer1[128];
unsigned int RXCounter1 = 0;
unsigned char rev_finish_flag1 = 0;
extern unsigned char idata g_cReceBuf[64];

void Uart1_IRQHandler(void) interrupt	4					  //中断接收函数 中断号为4    P188
{
	if(RI)											  //判断接收的数据是否接收完，当接收到第8位时 接收结束  RI会置1	  P265
	{
		RI = 0;										  //接收中断使能位清0
		g_cReceBuf[RXCounter1++] = SBUF;				  //将串口缓冲器SBUF的数据放到数据接收缓冲器RX0_Buffer[]中
		rev_finish_flag1 = 1;									  //将标志位置1方便主函数判断
	}

	if(TI)											  //判断发送的数据是否发送完，当发送到第8位时 发送结束  TI会置1	   P265
	{
		TI = 0;										  //将发送结束标志位 TI清0
		B_TI = 1;									  //将B_TI 置1 方便上面的Uart1_TxByte 函数判断
	}
}


//void Uart1_TxString(unsigned char *puts)			   
//{
//    for(; *puts != 0; puts++)
//	{
//        Uart1_TxByte(*puts);						   //以指针的形式将字符串分解为单个字符，调用上面的单个字符发送函数发送
//	}
//}


//void Uart1_TxByte(unsigned char dat)				   //串口1发送单个字符函数
//{
//    B_TI = 0;										   //将B_TI置0
//	SBUF = dat;										   //将发送的数据写入SBUF缓冲器中
//	while(!B_TI);									   //等待发送 缓冲器发送完数据
//	B_TI = 0;										   //将B_TI置位0
//}

//void Uart1_Senddata(unsigned char *DATA,unsigned char length)
//{
//	unsigned char i;
//	for(i=0;i<length;i++)
//		Uart1_TxByte(DATA[i]);
//}



