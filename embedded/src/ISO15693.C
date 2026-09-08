//#include <reg52.h>
#include <STC12C5A60S2.h>
#include <string.h>
#include "main.h"
#include "slrc632.h"
#include "iso15693.h" 
#include "delay.h"

extern struct TranSciveBuffer{unsigned char MfCommand;
                              unsigned int  MfLength;
                              unsigned char MfData[64];
                             };

//ËùÓÐº¯ÊýµÄ²ÎÊý²Î¼ûISO15693-3/10.3
//·µ»ØÊý¾ÝÔÚ´æÈërespÊ±È¥µôÁËflag×Ö½Ú
//µ±¸ÄÐ´¿¨Æ¬ÉÏÊý¾ÝÊ±£¨write or lock)Èç²Ù×÷µÄÊÇTI¿¨Æ¬ÉèflagsµÄbit6 Option_flag = 1£¬Èç²Ù×÷µÄÊÇI.CODE SLI¿¨Æ

/////////////////////////////////////////////////////////////////////
//ISO15693 INVENTORY
/////////////////////////////////////////////////////////////////////                           
char ISO15693_Inventory (unsigned char flags,
                         unsigned char AFI, 
                         unsigned char masklengh, 
                         unsigned char *uid, 
                         unsigned char *resp)
{
    unsigned char SndCNT, cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
        
    ClearBitMask(RegCoderControl, 0x80);
            
    MfComData.MfCommand = PCD_TRANSCEIVE;	
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_INVENTORY;
    SndCNT = 2;
    if (flags & 0x10)
    {
        MfComData.MfData[SndCNT] = AFI;		
        SndCNT++;
    }
    MfComData.MfData[SndCNT] = masklengh;
    SndCNT++;
    if (masklengh%8)
    {    cnt = masklengh/8 + 1;    }
    else
    {    cnt = masklengh/8;        }
    if (cnt)
    {    memcpy(&MfComData.MfData[SndCNT], uid, cnt);    }
    MfComData.MfLength  = cnt + SndCNT;

    status = ISO15693_Transceive(pi);
   
    if (status == MI_OK)
    {
        if (MfComData.MfLength != 0x50)
        {    status = MI_BITCOUNTERR;    }
        else
        {    memcpy(resp, &MfComData.MfData[1], 9);    }
    }     
    return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693 INVENTORY_16
/////////////////////////////////////////////////////////////////////                           
char ISO15693_Inventory16(unsigned char flags,
                          unsigned char AFI, 
                          unsigned char masklengh, 
                          unsigned char *uid, 
                          unsigned char *resplen, 
                          unsigned char *resp)
{
    unsigned char idata SndCNT, cnt, status, status1, i,j;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
    status = MI_COM_ERR;
    *resplen = 0;
    SetBitMask(RegChannelRedundancy, 0x04);   
    ClearBitMask(RegCoderControl, 0x80);
    
                
    MfComData.MfCommand = PCD_TRANSMIT;	
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_INVENTORY;
    SndCNT = 2;
    if (flags & 0x10)
    {
        MfComData.MfData[SndCNT] = AFI;		
        SndCNT++;
    }
    MfComData.MfData[SndCNT] = masklengh;
    SndCNT++;
    if (masklengh%8)
    {    cnt = masklengh/8 + 1;    }
    else
    {    cnt = masklengh/8;        }
    if (cnt)
    {    memcpy(&MfComData.MfData[SndCNT], uid, cnt);    }
    MfComData.MfLength  = cnt + SndCNT;

    status1 = ISO15693_Transceive(pi);

    j = 0;
    for (i=0; i<16; i++)
    {
         pi = &MfComData;
         ClearBitMask(RegChannelRedundancy, 0x04);
         SetBitMask(RegCoderControl, 0x80);
         SetBitMask(RegTxControl, 0x10);
         MfComData.MfCommand = PCD_TRANSCEIVE;
         MfComData.MfLength = 0;

         status1 = ISO15693_Transceive( pi );

         if ((status1 == MI_OK) && (MfComData.MfLength == 0x50))
         {
	         status = MI_OK;
			 *resplen += 9;
		     memcpy(resp+9*j, &MfComData.MfData[1], 9);	
             j++;    
         }
         if (*resplen >= 36)
         {   break;    }
	}
	return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693 Stay Quiet
/////////////////////////////////////////////////////////////////////
char ISO15693_Stay_Quiet(unsigned char flags, unsigned char *uid) 
{
    unsigned char status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;

    ClearBitMask(RegCoderControl, 0x80);
            
    MfComData.MfCommand = PCD_TRANSMIT;
    MfComData.MfLength  = 10;
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_STAY_QUIET;
    memcpy(&MfComData.MfData[2], uid, 8);

    status = ISO15693_Transceive(pi);
    return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Select 
/////////////////////////////////////////////////////////////////////
char ISO15693_Select(unsigned char flags, unsigned char *uid) 
{
    unsigned char status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;

    ClearBitMask(RegCoderControl, 0x80);
    
    MfComData.MfCommand = PCD_TRANSCEIVE;
    MfComData.MfLength  = 10;
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_SELECT;
    memcpy (&MfComData.MfData[2], uid, 8);

    status = ISO15693_Transceive(pi);
	
    if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
    {    status = MI_BITCOUNTERR;    }
    return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Reset_To_Ready
/////////////////////////////////////////////////////////////////////
char ISO15693_Reset_To_Ready(unsigned char flags, unsigned char *uid) 
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
        
    ClearBitMask(RegCoderControl, 0x80);

    MfComData.MfCommand = PCD_TRANSCEIVE;
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_RESET_TO_READY;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
        memcpy (&MfComData.MfData[2], uid, 8);
        cnt = cnt + 8;
    }

    MfComData.MfLength = cnt;

    status = ISO15693_Transceive(pi);
	
    if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
    {    status = MI_BITCOUNTERR;    }
    return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693_READ Single/Multiple Block(s)
/////////////////////////////////////////////////////////////////////
char ISO15693_Read_sm (unsigned char flags, 
                       unsigned char *uid, 
                       unsigned char blnr, 
                       unsigned char nbl, 
                       unsigned char *resplen, 
                       unsigned char *resp)
{
    unsigned char idata cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
    *resplen = 0;
        
    ClearBitMask(RegCoderControl, 0x80);
        
    if(nbl)
    {    nbl--;	}
    MfComData.MfCommand = PCD_TRANSCEIVE;
    MfComData.MfData[0] = flags;
    if (nbl)
    {    MfComData.MfData[1] = ISO15693_READ_MULTIPLE_BLOCKS;    }
    else
    {    MfComData.MfData[1] = ISO15693_READ_SINGLE_BLOCK;       }
    cnt = 2;
    if ((flags & 0x20) && !(flags & 0x10)) // flags & 0x20 - Addressflag 
				   // request flags & 0x10 - Selectflag request
    {
        memcpy (&MfComData.MfData[cnt], uid, 8);
        cnt = cnt + 8;
    }
    MfComData.MfData[cnt] = blnr;
    if (nbl)
    {
        cnt++;
        MfComData.MfData[cnt] = nbl;
    }

    MfComData.MfLength = cnt + 1;

    status = ISO15693_Transceive( pi );
	
    if (status == MI_OK)
    {
        *resplen = MfComData.MfLength/8 - 1;
        memcpy(resp, &MfComData.MfData[1], *resplen);
    }
    return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Write Single
/////////////////////////////////////////////////////////////////////
char ISO15693_Write_sm (unsigned char flags, 
                        unsigned char *uid, 
                        unsigned char blnr,
		                unsigned char *_data)                         
{
    char status;
    unsigned char cnt;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
    
    ClearBitMask(RegCoderControl, 0x80);
        
    if (flags & 0x40)
    {    MfComData.MfCommand = PCD_TRANSMIT;   }
    else
    {    MfComData.MfCommand = PCD_TRANSCEIVE;   }
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_WRITE_SINGLE_BLOCK;      
    cnt = 2;

    if (flags & 0x20) 
    {
         memcpy (&MfComData.MfData[2], uid, 8);
         cnt = cnt + 8;
    }
    MfComData.MfData[cnt] = blnr;
    cnt++;

    memcpy(&MfComData.MfData[cnt], _data, 4);
    cnt = cnt + 4;

    MfComData.MfLength = cnt;

    status = ISO15693_Transceive( pi );

    if (status != MI_OK)
    {    return status;   }
    else if (!(flags & 0x40)) 
    {
        if (MfComData.MfLength != 0x08)
        {    status = MI_BITCOUNTERR;    }
        return status;
    }
    else
    {
        DelayMs(10);
        pi = &MfComData;
    
        SetBitMask(RegCoderControl, 0x80);
        
        MfComData.MfCommand = PCD_TRANSCEIVE;
        MfComData.MfLength = 0;

        status = ISO15693_Transceive( pi );

        if ((status == MI_OK) && (MfComData.MfLength != 0x08))
        {    status = MI_BITCOUNTERR;    }
        return status;
     }
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Lock_Block 
/////////////////////////////////////////////////////////////////////
char ISO15693_Lock_Block (unsigned char flags, 
                          unsigned char *uid, 
                          unsigned char blnr)
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;

    ClearBitMask(RegCoderControl, 0x80);
    
    if (flags & 0x40)
    {    MfComData.MfCommand = PCD_TRANSMIT;   }
    else
    {    MfComData.MfCommand = PCD_TRANSCEIVE;   }
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_LOCK_BLOCK;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
         memcpy (&MfComData.MfData[2], uid, 8);
         cnt = cnt + 8;
    }
    MfComData.MfData[cnt] = blnr;

    MfComData.MfLength = cnt + 1;

    status = ISO15693_Transceive( pi );
	
    if (status != MI_OK)
    {    return status;   }
    else if (!(flags & 0x40)) 
    {
        if (MfComData.MfLength != 0x08)
        {    status = MI_BITCOUNTERR;    }
        return status;
    }
    else
    {
        DelayMs(10);
        pi = &MfComData;
    
        SetBitMask(RegCoderControl, 0x80);
        
        MfComData.MfCommand = PCD_TRANSCEIVE;
        MfComData.MfLength = 0;

        status = ISO15693_Transceive( pi );

        if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
        {    status = MI_BITCOUNTERR;    }
        return status;
     }
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Write_AFI
/////////////////////////////////////////////////////////////////////
char ISO15693_Write_AFI (unsigned char flags, 
                         unsigned char *uid, 
                         unsigned char AFI)
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
    
    ClearBitMask(RegCoderControl, 0x80);

    if (flags & 0x40)
    {    MfComData.MfCommand = PCD_TRANSMIT;   }
    else
    {    MfComData.MfCommand = PCD_TRANSCEIVE;   }
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_WRITE_AFI;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
         memcpy (&MfComData.MfData[2], uid, 8);
         cnt = cnt + 8;
    }
    MfComData.MfData[cnt] = AFI;

    MfComData.MfLength = cnt + 1;

    status = ISO15693_Transceive( pi );
	
    if (status != MI_OK)
    {    return status;   }
    else if (!(flags & 0x40)) 
    {
        if (MfComData.MfLength != 0x08)
        {    status = MI_BITCOUNTERR;    }
        return status;
    }
    else
    {
        DelayMs(10);
        pi = &MfComData;
    
        SetBitMask(RegCoderControl, 0x80);
        
        MfComData.MfCommand = PCD_TRANSCEIVE;
        MfComData.MfLength = 0;

        status = ISO15693_Transceive( pi );

        if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
        {    status = MI_BITCOUNTERR;    }
        return status;
     }
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Lock_AFI 
/////////////////////////////////////////////////////////////////////
char ISO15693_Lock_AFI (unsigned char flags, unsigned char *uid) 
{
    unsigned char idata cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
    
    ClearBitMask(RegCoderControl, 0x80); 
     
    if (flags & 0x40)
    {    MfComData.MfCommand = PCD_TRANSMIT;   }
    else
    {    MfComData.MfCommand = PCD_TRANSCEIVE;   }
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_LOCK_AFI;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
         memcpy (&MfComData.MfData[2], uid, 8);
         cnt = cnt + 8;
    }
    MfComData.MfLength = cnt;

    status = ISO15693_Transceive( pi );
	
    if (status != MI_OK)
    {    return status;   }
    else if (!(flags & 0x40)) 
    {
         if (MfComData.MfLength != 0x08)
         {    status = MI_BITCOUNTERR;    }
         return status;
    }
    else
    {
         DelayMs(10);
         pi = &MfComData;
    
         SetBitMask(RegCoderControl, 0x80);
        
         MfComData.MfCommand = PCD_TRANSCEIVE;
         MfComData.MfLength = 0;

         status = ISO15693_Transceive( pi );

         if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
         {    status = MI_BITCOUNTERR;    }
         return status;
     }
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Write_DSFID
/////////////////////////////////////////////////////////////////////
char ISO15693_Write_DSFID (unsigned char flags, 
                           unsigned char *uid, 
                           unsigned char DSFID)
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
    
    ClearBitMask(RegCoderControl, 0x80);

    if (flags & 0x40)
    {    MfComData.MfCommand = PCD_TRANSMIT;   }
    else
    {    MfComData.MfCommand = PCD_TRANSCEIVE;   }
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_WRITE_DSFID;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
         memcpy (&MfComData.MfData[2], uid, 8);
         cnt = cnt + 8;
    }
    MfComData.MfData[cnt] = DSFID;

    MfComData.MfLength = cnt + 1;

    status = ISO15693_Transceive( pi );
	
    if (status != MI_OK)
    {    return status;   }
    else if (!(flags & 0x40)) 
    {
        if (MfComData.MfLength != 0x08)
        {    status = MI_BITCOUNTERR;    }
        return status;
    }
    else
    {
        DelayMs(10);
        pi = &MfComData;
    
        SetBitMask(RegCoderControl, 0x80);
        
        MfComData.MfCommand = PCD_TRANSCEIVE;
        MfComData.MfLength = 0;

        status = ISO15693_Transceive( pi );

        if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
        {    status = MI_BITCOUNTERR;    }
        return status;
     }
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Lock_DSFID 
/////////////////////////////////////////////////////////////////////
char ISO15693_Lock_DSFID (unsigned char flags, unsigned char *uid)
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
      
    ClearBitMask(RegCoderControl, 0x80);
  
    if (flags & 0x40)
    {    MfComData.MfCommand = PCD_TRANSMIT;   }
    else
    {    MfComData.MfCommand = PCD_TRANSCEIVE;   }
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_LOCK_DSFID;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
		  // 0x10 - Selectflag request
    {
        memcpy (&MfComData.MfData[2], uid, 8);
        cnt = cnt + 8;
    }
    MfComData.MfLength = cnt;

    status = ISO15693_Transceive( pi );
	
    if (status != MI_OK)
    {    return status;   }
    else if (!(flags & 0x40)) 
    {
         if (MfComData.MfLength != 0x08)
         {    status = MI_BITCOUNTERR;    }
         return status;
    }
    else
    {
         DelayMs(10);
         pi = &MfComData;
    
         SetBitMask(RegCoderControl, 0x80);
        
         MfComData.MfCommand = PCD_TRANSCEIVE;
         MfComData.MfLength = 0;

         status = ISO15693_Transceive( pi );

         if ( (status == MI_OK) && (MfComData.MfLength != 0x08) )
         {    status = MI_BITCOUNTERR;    }
         return status;
     }
}

/////////////////////////////////////////////////////////////////////
//ISO15693_Get_System_Information 
/////////////////////////////////////////////////////////////////////
char ISO15693_Get_System_Information (unsigned char flags, 
                                      unsigned char *uid, 
                                      unsigned char *resplen, 
                                      unsigned char *resp)
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;
     
    ClearBitMask(RegCoderControl, 0x80);   
    MfComData.MfCommand = PCD_TRANSCEIVE;	
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_GET_SYSTEM_INFO;
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
	memcpy(&MfComData.MfData[2], uid, 8);
        cnt = cnt + 8;
    }

    MfComData.MfLength = cnt;

    status = ISO15693_Transceive( pi );
	
    if (status == MI_OK)
    {
        *resplen = MfComData.MfLength/8-1;
        memcpy(resp, &MfComData.MfData[1], *resplen);
    }
    return status;
}

/////////////////////////////////////////////////////////////////////
//ISO15693 Get nultiple Block security status 
/////////////////////////////////////////////////////////////////////
char ISO15693_Get_Multiple_Block_Security(unsigned char flags, 
                                          unsigned char *uid, 
                                          unsigned char blnr,
                                          unsigned char nbl, 
                                          unsigned char *resplen, 
                                          unsigned char *resp)
{
    unsigned char cnt, status;
    struct TranSciveBuffer MfComData;
    struct TranSciveBuffer *pi;
    pi = &MfComData;

    ClearBitMask(RegCoderControl, 0x80);
    if(nbl)
    {   nbl--;   }
    *resplen = 0;

    MfComData.MfCommand = PCD_TRANSCEIVE;	
    MfComData.MfData[0] = flags;
    MfComData.MfData[1] = ISO15693_GET_MULTIPLE_BLOCK_SECURITY;	
    cnt = 2;
    if (flags & 0x20) // flags & 0x20 - Adresflag request flags & 
			  // 0x10 - Selectflag request
    {
        memcpy (&MfComData.MfData[2], uid, 8);
        cnt = cnt + 8;
    }
    MfComData.MfData[cnt] = blnr;
    cnt++;
    MfComData.MfData[cnt] = nbl;

    MfComData.MfLength = cnt + 1;

    status = ISO15693_Transceive( pi );
	
    if (status == MI_OK)
    {
        *resplen = MfComData.MfLength/8-1;
        memcpy(resp, &MfComData.MfData[1], *resplen);
    }
    return status;
}


