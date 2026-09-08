#ifndef __MAIN_H
	#define __MAIN_H

//指定PCD接收缓冲值
#ifndef FSDI
#define FSDI 4
#endif
/////////////////////////////////////////////////////////////////////
//89C52特殊寄存器定义
/////////////////////////////////////////////////////////////////////
sfr16    RCAP2LH    =    0xCA;
sfr16    T2LH       =    0xCC;

//sfr      CHPENR     =    0xF6;
//sfr      CHPCON     =    0xBF;
//sfr      P4         =    0xD8;
/////////////////////////////////////////////////////////////////////
//端口定义
/////////////////////////////////////////////////////////////////////
//MFRC500
sbit     RC632_CE   =    P2^7;                   //RC500片选
sbit     RC632_RST  =    P3^4;                   //RC500ALE
sbit     sond       =    P3^3;
sbit     dog        =    P1^7;

sbit     bianma0    =    P1^0;
sbit     bianma1    =    P1^1;
sbit     bianma2    =    P1^2;

sbit     LED_ANT1   =    P4^0;
sbit     LED_ANT2   =    P2^0;
sbit     LED_ANT3   =    P2^1;
sbit     LED_ANT4   =    P2^2;
sbit     LED_ANT5   =    P2^3;
sbit     LED_ANT6   =    P2^4;
sbit     LED_ANT7   =    P2^5;
sbit     LED_ANT8   =    P4^4;


sbit     BUSY		=    P0^7;
//sbit     LCDRS		=    P2^0;
//sbit     LCDRW	 	=    P2^1;
//sbit     LCDEN		=    P2^2;
/////////////////////////////////////////////////////////////////////
//RC500的EEPROM定义
/////////////////////////////////////////////////////////////////////
#define  ICDEV_RC500_ADR 0x30
/////////////////////////////////////////////////////////////////////
//延时常数及波特率定义
/////////////////////////////////////////////////////////////////////
//#define  OSC_FREQ        22118400L
#define  OSC_FREQ        11059200L

#define  RCAP2_50us      65536L - OSC_FREQ/240417L
#define  RCAP2_1ms       65536L - OSC_FREQ/12021L
#define  RCAP2_10ms      65536L - OSC_FREQ/1200L
#define  TIME0_500us     65536L - OSC_FREQ/48000L
#define  TIME0_10ms      65536L - OSC_FREQ/1200L

#define BOUND115200       256 - (OSC_FREQ/192L)/115200L   // 255
#define BOUND57600        256 - (OSC_FREQ/192L)/57600L    // 254
#define BOUND38400        256 - (OSC_FREQ/192L)/38400L    // 253
#define BOUND28800        256 - (OSC_FREQ/192L)/28800L    // 252
#define BOUND19200        256 - (OSC_FREQ/192L)/19200L    // 250
#define BOUND14400        256 - (OSC_FREQ/192L)/14400L    // 248
#define BOUND9600         256 - (OSC_FREQ/192L)/9600L     // 244
#define BOUND4800         256 - (OSC_FREQ/192L)/9600L     // 
/////////////////////////////////////////////////////////////////////
//和上位机的通讯错误代码定义
/////////////////////////////////////////////////////////////////////
#define  FAULT10  10        //通用错误
#define  FAULT11  11        //不支持该命令
#define  FAULT12  12        //命令参数错
#define  FAULT13  13        //无卡
#define  FAULT14  14        //射频基站损坏

#define  FAULT20  20        //寻卡失败
#define  FAULT21  21        //卡复位失败
#define  FAULT22  22        //密码验证失败
#define  FAULT23  23        //读卡失败
#define  FAULT24  24        //写卡失败

/////////////////////////////////////////////////////////////////////
//函数原型
/////////////////////////////////////////////////////////////////////
void InitializeSystem();                                   
void Rc632Ready();                                         
void AnswerCommandOk();
void AnswerCommandOk1();
void AnswerOk(unsigned char *answerdata,unsigned int answernum);          
void AnswerErr(char faultcode);
                                 

void ComSetBound();
void ComGetHardModel();
void ComM632PcdConfigISOType();
void ComPcdAntenna();
void ComRequestA();
void ComAnticoll();
void ComSelect();
void ComHlta();
void ComAuthentication();
void ComM1Read();
void ComM1Write();
void ComM1Initval();
void ComM1Readval();
void ComM1Decrement();
void ComM1Increment();
void ComM1Restore();
void ComM1Transfer();

void ComTypeARst();
void ComTypeACOS();
void ComTypeBRst();
void ComCL_Deselect();
void ComHltb();
void ComRF020Check();  
void ComRF020Read();  
void ComRF020Write();
void ComRF020Lock();	
void ComRF020Count();	
void ComRF020Deselect();
void ComLight();
void ComSelectSR();     
void ComReadSR176(); 
void ComWriteSR176();
void ComProtectSR176();
void ComCompletionSR();
void ComReadSR4K();  
void ComWriteSR4K();      
void ComAuthSR4K();
void ComGetUIDSR4K();
void ComProtectSR4K();
void ComUL_PcdAnticoll();
void ComUL_PcdWrite();

void ComISO15693_Inventory16();
void ComISO15693_Inventory();
void ComISO15693_Stay_Quiet();
void ComISO15693_Select();
void ComISO15693_Reset_To_Ready();
void ComISO15693_Read_sm();
void ComISO15693_Write_sm();
void ComISO15693_Lock_Block();
void ComISO15693_Write_AFI();
void ComISO15693_Lock_AFI();
void ComISO15693_Write_DSFID();
void ComISO15693_Lock_DSFID();
void ComISO15693_Get_System_Information();
void ComISO15693_Get_Multiple_Block_Security();


#endif

