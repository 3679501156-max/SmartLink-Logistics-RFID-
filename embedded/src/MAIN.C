#include <STC12C5A60S2.h>
#include <string.h>
#include <intrins.h>
#include "main.h"
#include "slrc632.h"
#include "iso14443a.h"
#include "iso14443b.h"
#include "iso15693.h" 
#include "uart1.h"
#include "delay.h"


//Ӳ���汾         
unsigned char code hardmodel[18]  = {"RC632toUSB Ver2.0"};  

bit g_bReceOk;                                              //ȷ���յ���λ��ָ���־
bit g_bReceAA;                                              //���յ���λ�����͵�AA�ֽڱ�־
bit g_bRc632Ok;                                             //RC632��λ������־
bit g_bIblock;


unsigned int idata   g_cReceNum;                       //���յ���λ�����ֽ���
unsigned int  data g_cCommand;                              //���յ���������
unsigned char data g_cSNR[4];                               //M1�����к�
unsigned char g_cIcdevH;                                    //�豸���
unsigned char g_cIcdevL;                                    //�豸���
unsigned char g_cFWI;                                       //
unsigned char idata  g_cCidNad;                                    //
unsigned char idata g_cReceBuf[64];                         //����λ��ͨѶʱ�Ļ�����

unsigned char count=0;
unsigned char ant=0;
struct TranSciveBuffer{unsigned char MfCommand;
                       unsigned int  MfLength;
                       unsigned char MfData[64];
                      };
					  
extern unsigned int RXCounter1;
extern unsigned char rev_finish_flag1;

void BEEP(unsigned char i)
{
    unsigned char k;
	k=i*200;
    sond =  1;
	delay(k);
	sond =0;
}


void antsel(char i)
{
	switch(i)
	{
		case 1:			//ѡ��1������			 
			bianma0 =0;
            bianma1=0;
            bianma2=0;
		    LED_ANT1 = 1;
			P2 &= 0XC0;		//1100 0000
            LED_ANT8 = 0;			
			break;
		case 2:			//ѡ��2������
			bianma0=0;
			bianma1=0;
			bianma2=1;
			LED_ANT1 = 0;
			P2 &= 0XC0;
			P2 |= 0X01;		//0000 0001
			LED_ANT8 = 0;		
			break;
		case 3:			//ѡ��3������
			bianma0=0;
            bianma1=1;
            bianma2=0;
			LED_ANT1 = 0;
			P2 &= 0XC0;
			P2 |= 0X02;		//0000 0010
            LED_ANT8 = 0;
			break;
		case 4:			//ѡ��4������
		    bianma0=0;
            bianma1=1;
            bianma2=1;
			LED_ANT1 = 0;
			P2 &= 0XC0;
			P2 |= 0X04;		//0000 0100
            LED_ANT8 = 0;
			break;
		case 5:			//ѡ��5������
			bianma0=1;
            bianma1=0;
            bianma2=0;
			LED_ANT1 = 0;
			P2 &= 0XC0;
			P2 |= 0X08;		//0000 1000
            LED_ANT8 = 0;
		 	break;
		case 6:			//ѡ��6������
			bianma0=1;
      		bianma1=0;
        	bianma2=1;
		   	LED_ANT1 = 0;
			P2 &= 0XC0;
			P2 |= 0XD0;	//1101 0000
            LED_ANT8 = 0;
			break;
		case 7:			//ѡ��7������
			bianma0=1;
            bianma1=1;
            bianma2=0;
			LED_ANT1 = 0;
			P2 &= 0XC0;
			P2 |= 0XE0;	 //1110 0000
            LED_ANT8 = 0;
			break;
		case 8:			//ѡ��8������
			bianma0=1;
            bianma1=1;
            bianma2=1;
			LED_ANT1 = 0;
			P2 &= 0XC0;	   //1100 0000
            LED_ANT8 = 1;
			break;
		 }
	AnswerCommandOk();
}

void main( )
{    
	InitializeSystem( );
	Rc632Ready( ); 
	sond =0;

	P1M1 = 0x00;	   //P1.0��P1.1��P1.2�������
	P1M0 = 0x07;
	  
	P2M1 = 0x00;	   //P2.0-P2.5�������
	P2M0 = 0x3f;
	 
	P4M1 = 0x00;	   //P4.0��P4.4�������
	P4M0 = 0x11;
	  
	antsel(1);
	while ( 1 )						 
	{
		if(rev_finish_flag1==1)
		{
			delay_ms(20);
			rev_finish_flag1 = 0;
			RXCounter1 = 0;
			g_cCommand = ((unsigned int)(g_cReceBuf[7]<<8))+(unsigned int)g_cReceBuf[6];
			RC632_CE=0;   
       		switch(g_cCommand)	
			{
				case 0x11FF:
					antsel(g_cReceBuf[8]);      //ѡ������
					break;

				case 0x0101:
					ComSetBound();               
					break;

				case 0x0104:
					ComGetHardModel();           
					break;

				case 0x0108:
					ComM632PcdConfigISOType();   
					break;  

				case 0x010C:
					ComPcdAntenna();             
					break; 
                                  
				case 0x0201:
					ComRequestA();       //Ѱ��
					break;  

				case 0x0202:
					ComAnticoll();	    //����
					BEEP(2);			//����������������					
					break;        

         		case 0x0203:
					ComSelect();                 
					break;

				case 0x0204:
					ComHlta();                   
					break;

				case 0x0207:
					ComAuthentication();         
					break; 

				case 0x0208:
					ComM1Read();                 
					break;

				case 0x0209:
					ComM1Write();                
					break;

				case 0x020A:
					ComM1Initval();              
					break; 

				case 0x020B:
					ComM1Readval();              
					break;

        		case 0x020C:
               		ComM1Decrement();            
					break;

         		case 0x020D:
           			ComM1Increment();            
					break;  

         		case 0x020E:
         			ComM1Restore();              
					break;

             	case 0x020F:
         			ComM1Transfer();             
					break; 

            	case 0x0210:
          			ComTypeARst();               
					break; 

              	case 0x0211:
             		ComTypeACOS();               
					break; 

				case 0x0212:
              		ComUL_PcdAnticoll();         
					break; 

				case 0x0213:
           			ComUL_PcdWrite();            
					break;

        		case 0x0301:
            		ComTypeBRst();               
					break;  
                  // case 0x1E:
                  //      ComAttrib();    break;
           		case 0x0302:
               		ComHltb();                   
					break;

              	case 0x0303:
                	ComCL_Deselect();            
					break;    

           		case 0x0401:
              		ComRF020Check();             
					break; 

               case 0x0402:
                    ComRF020Read();              
					break;

           		case 0x0403:
                	ComRF020Write();             
					break;

       			case 0x0404:
               		ComRF020Lock();              
					break;

               	case 0x0405:	
                  	ComRF020Count();             
					break;

            	case 0x0406:	
           			ComRF020Deselect();         
						 break;

				case 0x0501:
                	ComSelectSR();               
					break;

           		case 0x0502:
               		ComCompletionSR();           
					break; 

           		case 0x0503:
                	ComReadSR176();              
					break;  

          		case 0x0504:
                 	ComWriteSR176();             
					break;   

 				case 0x0505:
          			ComProtectSR176();           
					break;  
           		case 0x0506:
      				ComReadSR4K();               
					break; 
					 
             	case 0x0507:
                	ComWriteSR4K();              
					break;
					      
           		case 0x0508:
            		ComAuthSR4K();               
					break;
					  
           		case 0x0509:
               		ComGetUIDSR4K();             
					break; 

           		case 0x050A:
                 	ComProtectSR4K();            
					break; 

         		case 0x1000:
               		ComISO15693_Inventory16();   
					break;

           		case 0x1001:
            		ComISO15693_Inventory();     
					break;

          		case 0x1002:
              		ComISO15693_Stay_Quiet();    
					break;

				case 0x1003:
            		ComISO15693_Select();        
					break;

           		case 0x1004:
               		ComISO15693_Reset_To_Ready();
					break;

         		case 0x1005:
             		ComISO15693_Read_sm();       
					break;

          		case 0x1006:
              		ComISO15693_Write_sm();      
					break;

            	case 0x1007:
                	ComISO15693_Lock_Block();    
					break;

            	case 0x1008:
                   	ComISO15693_Write_AFI();     
					break;

          		case 0x1009:
            		ComISO15693_Lock_AFI();      
					break;

            	case 0x100A:
             		ComISO15693_Write_DSFID();   
					break;

            	case 0x100B:
                	ComISO15693_Lock_DSFID();    
					break;

             	case 0x100C:
                  	ComISO15693_Get_System_Information();     
					break;

         		case 0x100D:
                	ComISO15693_Get_Multiple_Block_Security();
					break;  

             	default:
             		AnswerErr( FAULT11 );         
					break;
				}

             RC632_CE=1;
             ES = 1;
			 EA=1;
          }
     }
}



/////////////////////////////////////////////////////////////////////
//ϵͳ��ʼ��
/////////////////////////////////////////////////////////////////////

void InitializeSystem()
{
    TMOD &= 0x0F;
    TMOD |= 0x21;
    PCON |= 0x80;
    SCON  = 0x50;
    TH1 = TL1 = BOUND9600; 
    TR1=1;
   	P3M1 = 0x00;	        //��ʼ��P3.3��Ϊ׼˫���
    P3M0 = 0x08;
    P0 = P1 = P2 = P3 = 0xFF;
   
    IE |= 0x90;
}


/////////////////////////////////////////////////////////////////////
//��ʼ��RC632
/////////////////////////////////////////////////////////////////////
void Rc632Ready()
{
    char status;
    delay(100);
    status = PcdReset();
    if(status != MI_OK)
    {
        delay(10);
        status = PcdReset();
    } 
    if(status != MI_OK)
    {
        delay(10);
        status = PcdReset();
    } 
    if(status == MI_OK)
    {
        g_bRc632Ok = 1;
    }       
}
	
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵����ò���������
/////////////////////////////////////////////////////////////////////
void ComSetBound()
{
    unsigned char bound = g_cReceBuf[6];
    if (bound > 7)
    {   AnswerErr(FAULT12);    }
    else
    {
    	AnswerCommandOk();
    	TR1 = 0;
         
    	switch(bound)
        {
                 case 0:
                      TH1=TL1=BOUND4800;
                      break;
                 case 1:
                      TH1=TL1=BOUND9600;
                      break;
                 case 2:
                      TH1=TL1=BOUND14400;
                      break;
                 case 3:
                      TH1=TL1=BOUND19200;
                      break;
                 case 4:
                      TH1=TL1=BOUND28800;
                      break;
                 case 5:
                      TH1=TL1=BOUND38400;
                      break;
                 case 6:
                      TH1=TL1=BOUND57600;
                      break;
                 case 7:
                      TH1=TL1=BOUND115200;
                      break;
                 default:
                      break;
        }
    	TR1 = 1;
     }   	
}


/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵Ķ�ȡӲ���汾������
/////////////////////////////////////////////////////////////////////
void ComGetHardModel()
{
    memcpy(&g_cReceBuf[0], &hardmodel[0], sizeof(hardmodel));
    AnswerOk(&g_cReceBuf[0], sizeof(hardmodel));
}    

    
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵�����RC632Э�����ISO14443A/B��ISO15693
/////////////////////////////////////////////////////////////////////
void ComM632PcdConfigISOType()
{
     if (MI_OK == PcdConfigISOType(g_cReceBuf[6]))
     {    AnswerCommandOk();    }
     else
     {    AnswerErr(-1);   }  
} 
   
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵���������
/////////////////////////////////////////////////////////////////////
void ComPcdAntenna()
{
    char status;
    if (!g_cReceBuf[6])
    {   status = PcdAntennaOff();   }
    else
    {  
        DelayMs(10); 
        status = PcdAntennaOn();
        DelayMs(10);
    }
    if (status == MI_OK)
    {   AnswerCommandOk();    }
    else 
    {   AnswerErr(FAULT10);   }
}    

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵�ѰA������
/////////////////////////////////////////////////////////////////////
void ComRequestA()
{
    unsigned char atq[2];
	char status;
	status = PcdRequest(g_cReceBuf[8], atq);
	if (status != MI_OK)
	{    status = PcdRequest(g_cReceBuf[8], atq);   }
    if (status == MI_OK)
    {    AnswerOk(atq,2);     }
    else
    {    AnswerErr(FAULT20);   }    	
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵�A������ײ����
/////////////////////////////////////////////////////////////////////
void ComAnticoll()
{ 
    if (MI_OK == PcdAnticoll(&g_cSNR))
    {    AnswerOk(&g_cSNR,4);  }
    else
    {    AnswerErr(FAULT10);   }    	
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵�A����������
/////////////////////////////////////////////////////////////////////
void ComSelect()
{
    if (MI_OK == PcdSelect(&g_cReceBuf[6], &g_cReceBuf[0]))
    {    AnswerOk(&g_cReceBuf[0], 1);      }
    else
    {    AnswerErr(FAULT10);   }    	
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵�A����������
/////////////////////////////////////////////////////////////////////
void ComHlta()
{
    if (MI_OK == PcdHalt())
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT10);   }    	
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ�����͵�A����֤��Կ����
/////////////////////////////////////////////////////////////////////
void ComAuthentication()
{	
    char status = MI_COM_ERR;
    unsigned char *pkeys,*pSNR;
    pkeys = &g_cReceBuf[20];
    pSNR  = &g_cSNR;
    if (MI_OK == ChangeCodeKey(&g_cReceBuf[8],pkeys))                       //ת����Կ��ʽ
    {    
    	if (MI_OK == PcdAuthKey(pkeys))                                     //������Կ��RC500FIFO
        {
             status = PcdAuthState(g_cReceBuf[6], g_cReceBuf[7], pSNR);     //��֤��Կ
        }
    }
    if (status == MI_OK)
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT22);   }
}    

///////////////////  //////////////////////////////////////////////////
//��Ӧ��λ����M1������
/////////////////////////////////////////////////////////////////////
void ComM1Read()
{
    if (MI_OK == PcdRead(g_cReceBuf[6], &g_cReceBuf[0]))
    {	 AnswerOk(&g_cReceBuf[0], 16);  }
    else
    {    AnswerErr(FAULT23);            }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��дM1������
/////////////////////////////////////////////////////////////////////
void ComM1Write()
{
    if (MI_OK == PcdWrite(g_cReceBuf[6], &g_cReceBuf[7]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ����ʼ��Ǯ������
/////////////////////////////////////////////////////////////////////
void ComM1Initval()
{
    g_cReceBuf[11]=~g_cReceBuf[7];g_cReceBuf[12]=~g_cReceBuf[8];
    g_cReceBuf[13]=~g_cReceBuf[9];g_cReceBuf[14]=~g_cReceBuf[10];
    g_cReceBuf[15]=g_cReceBuf[7];g_cReceBuf[16]=g_cReceBuf[8];
    g_cReceBuf[17]=g_cReceBuf[9];g_cReceBuf[18]=g_cReceBuf[10];
    g_cReceBuf[19]=g_cReceBuf[6];g_cReceBuf[20]=~g_cReceBuf[6];
    g_cReceBuf[21]=g_cReceBuf[6];g_cReceBuf[22]=~g_cReceBuf[6];
    if (MI_OK == PcdWrite(g_cReceBuf[6], &g_cReceBuf[7]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ����Ǯ������
/////////////////////////////////////////////////////////////////////
void ComM1Readval()
{
    if (MI_OK == PcdRead(g_cReceBuf[6], &g_cReceBuf[0]))
    {	 AnswerOk(&g_cReceBuf[0], 4);   }
    else
    {    AnswerErr(FAULT23);         }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ���ۿ�����
/////////////////////////////////////////////////////////////////////
void ComM1Decrement()
{
    if (MI_OK == PcdValue(PICC_DECREMENT, g_cReceBuf[6], &g_cReceBuf[7]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}    
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ����ֵ����
/////////////////////////////////////////////////////////////////////
void ComM1Increment()
{
    if (MI_OK == PcdValue(PICC_INCREMENT, g_cReceBuf[6], &g_cReceBuf[7]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
} 
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��M1���ش�����
/////////////////////////////////////////////////////////////////////
void ComM1Restore()
{
    if (MI_OK == PcdRestore(g_cReceBuf[6]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT23);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��M1��ֵ��������
/////////////////////////////////////////////////////////////////////
void ComM1Transfer()
{
    if (MI_OK == PcdTransfer(g_cReceBuf[6]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ultra light����ײ����
/////////////////////////////////////////////////////////////////////
void ComUL_PcdAnticoll()
{
    if (MI_OK == UL_PcdAnticoll(&g_cReceBuf[0]))
    {   AnswerOk(&g_cReceBuf[0], 7);  }
    else
    {   AnswerErr(FAULT10);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ultra lightд������
/////////////////////////////////////////////////////////////////////
void ComUL_PcdWrite()
{
    if (MI_OK == UL_PcdWrite(g_cReceBuf[6], &g_cReceBuf[7]))
    {   AnswerCommandOk();   }
    else
    {   AnswerErr(FAULT24);  }    
}



/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��TYPEA���߼���λ����
/////////////////////////////////////////////////////////////////////
void ComTypeARst()
{
    unsigned char status,i;
    i = (FSDI << 4) & 0xF0;
    status = PcdRequest(g_cReceBuf[6], &g_cReceBuf[0]);
    
    if (status != MI_OK)
    {   status = PcdRequest(g_cReceBuf[6], &g_cReceBuf[0]);   }

    if (status == MI_OK)
    {   status =  PcdAnticoll(&g_cReceBuf[1]);   }
    
    if (status == MI_OK)
    {   status =  PcdSelect(&g_cReceBuf[1], &g_cReceBuf[6]);   }
    

    if (status == MI_OK)
    {	
        g_cFWI         = 0xff;//g_cReceBuf[8]>>4;
        g_cReceBuf[0] += 4;
        g_cCidNad      = 0;//(g_cReceBuf[9] & 0x03) << 2;
        AnswerOk(&g_cReceBuf[1], g_cReceBuf[0]);
    }
    else
    {   AnswerErr(FAULT21);    }
}   

void ComTypeACOS()
{
    g_cReceBuf[0] -= 5;
    if (MI_OK == MifareProCom(g_cCidNad, g_cFWI, &g_cReceBuf[0], &g_cReceBuf[6]))
    {	AnswerOk(&g_cReceBuf[6], g_cReceBuf[0]);   }
    else
    {   AnswerErr(FAULT10);    }
} 
 
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ���߼���λTYPEB������
/////////////////////////////////////////////////////////////////////
/*
void ComTypeBRst()
{
    unsigned char status;
	
    if ((status = M531PiccRequestB(g_cReceBuf[6], 0, 0, &g_cReceBuf[0])) == MI_OK) 
    {	
    	g_cFWI    = 0xFF;//g_cReceBuf[11] >> 4; 
    	g_cCidNad = 8;//((g_cReceBuf[11]&0x02)<<1) | ((g_cReceBuf[11]&0x01)<<3);
 //       status = M531PiccAttrib(&g_cReceBuf[1], g_cReceBuf[10]&0x0F, &g_cReceBuf[12]);   
  //  }

 //   if (status == MI_OK)		{
       AnswerOk(&g_cReceBuf[0], 12);   }
    else
    {   AnswerErr(FAULT21);    }
}
*/

void ComTypeBRst()
{
    unsigned char status;
	
    if ((status = M531PiccRequestB(g_cReceBuf[6], 0, 0, &g_cReceBuf[0])) == MI_OK) 							 
    {	
    	g_cFWI    = 0xFF;//g_cReceBuf[11] >> 4; 
    	g_cCidNad = 8;//((g_cReceBuf[11]&0x02)<<1) | ((g_cReceBuf[11]&0x01)<<3);
        status = M531PiccAttrib(&g_cReceBuf[1], g_cReceBuf[10]&0x0F, &g_cReceBuf[12]);   
    }

    if (status == MI_OK)
    { 
	if ((status = Get_UID_TypeB(&g_cReceBuf[0])) == MI_OK)  
	AnswerOk(&g_cReceBuf[0], 12);   }
    else
    {   AnswerErr(FAULT21);    }

}	    	
	    	

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��HLTB3����
/////////////////////////////////////////////////////////////////////
void ComHltb()
{
    if (MI_OK == M531PiccHltb(&g_cReceBuf[6]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT10);   }
	M531PiccAttrib(&g_cReceBuf[1], g_cReceBuf[10]&0x0F, &g_cReceBuf[12]);
} 

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��HLTB4����
/////////////////////////////////////////////////////////////////////
void ComCL_Deselect()
{
    if (MI_OK == CL_Deselect(0))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT10);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��AT88RF020����֤��Կ����
/////////////////////////////////////////////////////////////////////
void ComRF020Check()	
{
    if (MI_OK == At88rf020Check(&g_cReceBuf[6]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT22);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��AT88RF020��������
/////////////////////////////////////////////////////////////////////
void ComRF020Read()	
{
    if (MI_OK == At88rf020Read(g_cReceBuf[6], &g_cReceBuf[0]))
    {    AnswerOk(&g_cReceBuf[0],8);   }
    else
    {    AnswerErr(FAULT23);         }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��AT88RF020��д����
/////////////////////////////////////////////////////////////////////
void ComRF020Write()	
{
    if (MI_OK == At88rf020Write(g_cReceBuf[6], &g_cReceBuf[7]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��AT88RF020��LOCK����
/////////////////////////////////////////////////////////////////////
void ComRF020Lock()	
{
    if (MI_OK == At88rf020Lock(&g_cReceBuf[6]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��AT88RF020��COUNT����
/////////////////////////////////////////////////////////////////////
void ComRF020Count()	
{
    if (MI_OK == At88rf020Count(&g_cReceBuf[6]))
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT24);   }
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��AT88RF020��DESELECT����
/////////////////////////////////////////////////////////////////////
void ComRF020Deselect()	
{
    if (MI_OK == At88rf020Deselect())
    {    AnswerCommandOk();    }
    else
    {    AnswerErr(FAULT10);   }
}


/////////////////////////////////////////////////////////////////////
//��Ӧ��λ������ST��Ƭ����
/////////////////////////////////////////////////////////////////////
void ComSelectSR()
{
    if(MI_OK == SelectSR(&g_cReceBuf[0]))
    {    AnswerOk(&g_cReceBuf[0],1);   }
    else
    {    AnswerErr(FAULT20);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SR176��������
/////////////////////////////////////////////////////////////////////
void ComReadSR176()
{
    if (MI_OK == ReadSR176(g_cReceBuf[6], &g_cReceBuf[0]))
    {    AnswerOk(&g_cReceBuf[0],2);   }
    else
    {    AnswerErr(FAULT23);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SR176д������
/////////////////////////////////////////////////////////////////////
void ComWriteSR176()
{
    char status;
    if((status = WriteSR176(g_cReceBuf[6], &g_cReceBuf[7])) == MI_OK)
    {
        DelayMs(5);
        status = ReadSR176(g_cReceBuf[6], &g_cReceBuf[0]);
        if((status==MI_OK) && (g_cReceBuf[0]==g_cReceBuf[7]) && (g_cReceBuf[1]==g_cReceBuf[8]))
        {   AnswerCommandOk();   }
        else
        {   AnswerErr(FAULT24);  } 
    }
    else
    {    AnswerErr(FAULT24);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SR176����������
/////////////////////////////////////////////////////////////////////
void ComProtectSR176()
{
    char status;
    if ((status = GetProtSR176(g_cReceBuf[0])) == MI_OK)
    {
        status = ProtectSR176(g_cReceBuf[6]);
        if (status == MI_OK)
        {
             DelayMs(5);
             status = GetProtSR176(g_cReceBuf[1]);
             if ((g_cReceBuf[0]|g_cReceBuf[6]) != g_cReceBuf[1])
    	     {    status = MI_COM_ERR;   }
        }
    }    
    if (status == MI_OK) 
    {   AnswerCommandOk();   }
    else
    {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SR176��COMPLETION����
/////////////////////////////////////////////////////////////////////
void ComCompletionSR()
{
    if (MI_OK == CompletionSR())
    {    AnswerCommandOk();   }
    else
    {    AnswerErr(FAULT10);  }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SRIX4K��������
/////////////////////////////////////////////////////////////////////
void ComReadSR4K()
{
    if (MI_OK == ReadSR4K(g_cReceBuf[6], &g_cReceBuf[0]))
    {    AnswerOk(&g_cReceBuf[0],4);    }
    else
    {    AnswerErr(FAULT23);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SRIX4Kд������
/////////////////////////////////////////////////////////////////////
void ComWriteSR4K()
{
    char status;
    if ((status = WriteSR4K(g_cReceBuf[6], &g_cReceBuf[7])) == MI_OK)
    {
        DelayMs(7);
        status = ReadSR4K(g_cReceBuf[6], &g_cReceBuf[0]);
        if ((status==MI_OK) && (g_cReceBuf[0]==g_cReceBuf[7]) && (g_cReceBuf[1]==g_cReceBuf[8])
            && (g_cReceBuf[2]==g_cReceBuf[9]) && (g_cReceBuf[3]==g_cReceBuf[10]))
        {   AnswerCommandOk();   }
        else
        {   AnswerErr(FAULT24);  } 
    }
    else
    {   AnswerErr(FAULT24);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SRIX4K��AUTHENTICATE����
/////////////////////////////////////////////////////////////////////
void ComAuthSR4K()
{
    if (MI_OK == AuthSR4K(&g_cReceBuf[6], &g_cReceBuf[0]))
    {   AnswerOk(&g_cReceBuf[0], 3);  }
    else
    {   AnswerErr(FAULT22);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SRIX4K��UID����
/////////////////////////////////////////////////////////////////////
void ComGetUIDSR4K()
{
    if (MI_OK == GetUIDSR4K(&g_cReceBuf[0]))
    {   AnswerOk(&g_cReceBuf[0], 8);  }
    else
    {   AnswerErr(FAULT23);    }    
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��SRIX4K����������
/////////////////////////////////////////////////////////////////////
void ComProtectSR4K()
{
    char status;
    if ((status = ReadSR4K(0xFF, &g_cReceBuf[0])) == MI_OK)
    {
        status = WriteSR4K(0xFF, &g_cReceBuf[6]);
        if (status == MI_OK)
        {
             DelayMs(7);
             status = ReadSR4K(0xFF, &g_cReceBuf[1]);
             if ((g_cReceBuf[0]&g_cReceBuf[6]) != g_cReceBuf[1])
    	     {    status = MI_COM_ERR;   }
        }
    }    
    if (status == MI_OK )
    {   AnswerCommandOk();   }
    else
    {   AnswerErr(FAULT24);  } 
}


/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Inventory����
/////////////////////////////////////////////////////////////////////
void ComISO15693_Inventory16()
{
     if (MI_OK == ISO15693_Inventory16(0x16,0x00,0x00,&g_cReceBuf[0],&g_cReceBuf[0], &g_cReceBuf[1]))
     {   AnswerOk(&g_cReceBuf[1], g_cReceBuf[0]);  }
     else
     {   AnswerErr( FAULT20 );   } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Inventory����
/////////////////////////////////////////////////////////////////////
void ComISO15693_Inventory()
{
     if (MI_OK == ISO15693_Inventory(0x36,0x00,0x00,&g_cReceBuf[0],&g_cReceBuf[0]))
     {   AnswerOk(&g_cReceBuf[0], 9);  }
     else
     {   AnswerErr( FAULT20 );   } 
}
     
/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Stay_Quiet����
/////////////////////////////////////////////////////////////////////
void ComISO15693_Stay_Quiet()
{
     if (MI_OK == ISO15693_Stay_Quiet(0x22, &g_cReceBuf[6])) 
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT10);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Select����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Select()
{
     if (MI_OK == ISO15693_Select(0x22, &g_cReceBuf[6]))
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT10);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Reset_To_Ready����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Reset_To_Ready()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Reset_To_Ready(flags, &g_cReceBuf[7]) )
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT10);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Read����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Read_sm()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Read_sm(flags,&g_cReceBuf[7],g_cReceBuf[15],g_cReceBuf[16],&g_cReceBuf[0],&g_cReceBuf[1])) 
     {   AnswerOk(&g_cReceBuf[1],g_cReceBuf[0]);  }
     else
     {   AnswerErr(FAULT23);    } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Write����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Write_sm()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Write_sm(flags, &g_cReceBuf[7], g_cReceBuf[15], &g_cReceBuf[16]) )
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Lock_Block����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Lock_Block()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Lock_Block(flags, &g_cReceBuf[7], g_cReceBuf[15]))
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Write_AFI����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Write_AFI()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Write_AFI(flags, &g_cReceBuf[7], g_cReceBuf[15])) 
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Lock_AFI����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Lock_AFI()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Lock_AFI(flags, &g_cReceBuf[7]) )
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Write_DSFID����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Write_DSFID()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Write_DSFID(flags, &g_cReceBuf[7], g_cReceBuf[15]) )
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Lock_DSFID����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Lock_DSFID()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Lock_DSFID(flags, &g_cReceBuf[7])) 
     {   AnswerCommandOk();   }
     else
     {   AnswerErr(FAULT24);  } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Get_System_Information����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Get_System_Information()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Get_System_Information(flags, &g_cReceBuf[7], &g_cReceBuf[0], &g_cReceBuf[1])) 
     {   AnswerOk(&g_cReceBuf[1],g_cReceBuf[0]);  }
     else
     {   AnswerErr(FAULT23);   } 
}

/////////////////////////////////////////////////////////////////////
//��Ӧ��λ��ISO15693_Get_Multiple_Block_Security����
/////////////////////////////////////////////////////////////////////     
void ComISO15693_Get_Multiple_Block_Security()
{
     unsigned char flags = 0x02;
     flags |= g_cReceBuf[6] << 4;
     if (MI_OK == ISO15693_Get_Multiple_Block_Security(flags,&g_cReceBuf[7],g_cReceBuf[15],g_cReceBuf[16],&g_cReceBuf[0],&g_cReceBuf[1])) 
     {   AnswerOk(&g_cReceBuf[1],g_cReceBuf[0]);  }
     else
     {   AnswerErr(FAULT23);  } 
}

/////////////////////////////////////////////////////////////////////
//��ȷִ������λ��ָ�Ӧ���޷������ݣ�
/////////////////////////////////////////////////////////////////////
void AnswerCommandOk()
{    
     unsigned char i,chkdata;
     chkdata = 0;
     
     TI   = 0;                         //��������ͷ          
     SBUF = 0xAA;
     while (!TI);           
     TI   = 0;
     SBUF = 0xBB;
     while (!TI);
     
     TI   = 0;                         //���ͳ�����
     SBUF = 0x06;
     while (!TI);           
     TI   = 0;
     SBUF = 0x00; 
     while (!TI);           
          
     TI   = 0;                         //�����豸��ʶ
     SBUF = g_cIcdevH;
     while (!TI);
     if (g_cIcdevH == 0xAA)
     {
     	TI   = 0;
     	SBUF = 0;
     	while (!TI);
     }
     TI   = 0; 
     SBUF = g_cIcdevL; 
     while (!TI);
     if (g_cIcdevL == 0xAA)
     {
     	TI   = 0;
     	SBUF = 0;
     	while (!TI);
     }
     
     TI   = 0;                         //����������                     
     i = (unsigned char)(g_cCommand & 0xFF);
     SBUF = i;
     chkdata ^= i;
     while (!TI);

     TI   = 0;                         //���������� 
     i = (unsigned char)((g_cCommand >>8) & 0xFF);
     SBUF = i;
     chkdata ^= i;
     while (!TI);

     TI   = 0;                         //����״̬��
     SBUF = 0;
     while (!TI);           
     
     TI   = 0;                         //����Ч����
     chkdata ^= g_cIcdevH^ g_cIcdevL;
     SBUF = chkdata;
     while (!TI);           
     if (chkdata == 0xAA)
     {
     	TI   = 0;
     	SBUF = 0;
     	while (!TI);
     }
     TI = 0;
     ES = 1;
}

/////////////////////////////////////////////////////////////////////
//δ����ȷִ����λ��ָ�Ӧ��
//input:faultcode = �������
/////////////////////////////////////////////////////////////////////
void AnswerErr(char faultcode)
{    
     unsigned char i,chkdata;
     chkdata = 0;

     TI   = 0;                         //��������ͷ          
     SBUF = 0xAA;
     while (!TI);           
     TI   = 0;
     SBUF = 0xBB;
     while (!TI);
     
     TI   = 0;                         //���ͳ�����
     SBUF = 0x06;
     while (!TI);           
     TI   = 0;
     SBUF = 0x00; 
     while (!TI);           
          
     TI   = 0;                         //�����豸��ʶ
     SBUF = g_cIcdevH;
     while (!TI);
     if (g_cIcdevH == 0xAA)
     {
     	TI   = 0;
     	SBUF = 0;
     	while (!TI);
     }
     TI   = 0; 
     SBUF = g_cIcdevL; 
     while (!TI);
     if (g_cIcdevL == 0xAA)
     {
     	TI   = 0;
     	SBUF = 0;
     	while (!TI);
     }
     
     TI   = 0;                         //����������                     
     i = (unsigned char)(g_cCommand & 0xFF);
	 SBUF = i;
	 chkdata ^= i;
     while (!TI);

	 TI   = 0;                         //���������� 
     i = (unsigned char)((g_cCommand >>8) & 0xFF);
	 SBUF = i;
	 chkdata ^= i;
     while (!TI);

     TI   = 0;                         //���ʹ������
     SBUF = faultcode;
     while (!TI);              
     
     chkdata = g_cIcdevH ^ g_cIcdevL ^ faultcode;
     TI   = 0;                         //Ч����
     SBUF = chkdata;
     while (!TI);
     
     TI   = 0;
     ES   = 1;
}