#include <intrins.h>
#include "delay.h"



void delay(unsigned int i)
{
	unsigned char j;
	while(i--) 
		for(j=0;j<200;j++);
}


void DelayMs(unsigned int _MS)
{
	unsigned char  i=0;
	while(_MS--)
	{
       for(i=0;i<120;i++)
	  {
		 _nop_();_nop_();_nop_();_nop_();
	  
	  }
   }
}
void Delay_50us(unsigned char _50us)
{
    unsigned char i;
	while(_50us--)
	for(i=0;i<25;i++);
}

void delay_ms(unsigned int num)
{
    unsigned int x,y;
    for(x=num; x>0; x--)
      for(y=500; y>0; y--);
}
