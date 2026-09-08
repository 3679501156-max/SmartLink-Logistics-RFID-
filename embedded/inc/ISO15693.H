/////////////////////////////////////////////////////////////////////
//ISO15693 COMMAND
///////////////////////////////////////////////////////////////////// 
#define	ISO15693_INVENTORY                      0x01
#define	ISO15693_STAY_QUIET                     0x02
#define	ISO15693_READ_SINGLE_BLOCK              0x20
#define	ISO15693_WRITE_SINGLE_BLOCK             0x21
#define	ISO15693_LOCK_BLOCK                     0x22
#define	ISO15693_READ_MULTIPLE_BLOCKS           0x23
#define	ISO15693_WRITE_MULTIPLE_BLOCKS          0x24
#define	ISO15693_SELECT                         0x25
#define	ISO15693_RESET_TO_READY                 0x26
#define	ISO15693_WRITE_AFI                      0x27
#define	ISO15693_LOCK_AFI                       0x28
#define	ISO15693_WRITE_DSFID                    0x29
#define	ISO15693_LOCK_DSFID                     0x2A
#define	ISO15693_GET_SYSTEM_INFO                0x2B
#define	ISO15693_GET_MULTIPLE_BLOCK_SECURITY    0x2C

/////////////////////////////////////////////////////////////////////
//		ISO15693 INVENTORY
/////////////////////////////////////////////////////////////////////   
char ISO15693_Inventory (unsigned char flags,
                         unsigned char AFI, 
                         unsigned char masklengh, 
                         unsigned char *uid, 
                         unsigned char *resp);

/////////////////////////////////////////////////////////////////////
//		ISO15693 INVENTORY_16
/////////////////////////////////////////////////////////////////////                           
char ISO15693_Inventory16(unsigned char flags,
                          unsigned char AFI, 
                          unsigned char masklengh, 
                          unsigned char *uid, 
                          unsigned char *resplen, 
                          unsigned char *resp);

/////////////////////////////////////////////////////////////////////
//		ISO15693 Stay Quiet
/////////////////////////////////////////////////////////////////////
char ISO15693_Stay_Quiet (unsigned char flags, 
                          unsigned char *uid);

/////////////////////////////////////////////////////////////////////
//		ISO15693 Select 
/////////////////////////////////////////////////////////////////////
char ISO15693_Select (unsigned char flags, 
                      unsigned char *uid); 

/////////////////////////////////////////////////////////////////////
//		ISO15693  Reset To Ready
/////////////////////////////////////////////////////////////////////
char ISO15693_Reset_To_Ready (unsigned char flags, 
                              unsigned char *uid); 
                              
/////////////////////////////////////////////////////////////////////
//     		ISO15693 READ Single / Multiple Block(s
/////////////////////////////////////////////////////////////////////
char ISO15693_Read_sm (unsigned char flags, 
                       unsigned char *uid, 
                       unsigned char blnr, 
                       unsigned char nbl, 
                       unsigned char *resplen, 
                       unsigned char *resp);  
                       
/////////////////////////////////////////////////////////////////////
//		ISO15693  Write Single Block
/////////////////////////////////////////////////////////////////////
char ISO15693_Write_sm (unsigned char flags, 
                        unsigned char *uid, 
                        unsigned char blnr,
                        unsigned char *_data);                         
                        
/////////////////////////////////////////////////////////////////////
// 		ISO15693 Lock Block 
/////////////////////////////////////////////////////////////////////
char ISO15693_Lock_Block (unsigned char flags, 
                          unsigned char *uid, 
                          unsigned char blnr);
                          
/////////////////////////////////////////////////////////////////////
//		ISO15693  Write AFI
/////////////////////////////////////////////////////////////////////
char ISO15693_Write_AFI (unsigned char flags, 
                         unsigned char *uid, 
                         unsigned char AFI);
                         
/////////////////////////////////////////////////////////////////////
//		ISO15693 Lock AFI 
/////////////////////////////////////////////////////////////////////
char ISO15693_Lock_AFI (unsigned char flags, 
                        unsigned char *uid);
                        
/////////////////////////////////////////////////////////////////////
//		ISO15693  Write DSFID
/////////////////////////////////////////////////////////////////////
char ISO15693_Write_DSFID (unsigned char flags, 
                           unsigned char *uid, 
                           unsigned char DSFID);
                           
/////////////////////////////////////////////////////////////////////
//		ISO15693 Lock DSFID 
/////////////////////////////////////////////////////////////////////
char ISO15693_Lock_DSFID (unsigned char flags, 
                          unsigned char *uid);
                          
/////////////////////////////////////////////////////////////////////
//		ISO15693 Get System Information 
/////////////////////////////////////////////////////////////////////
char ISO15693_Get_System_Information (unsigned char flags, 
                                      unsigned char *uid, 
                                      unsigned char *resplen, 
                                      unsigned char *resp);
                                      
/////////////////////////////////////////////////////////////////////
//		ISO15693 Get nultiple Block security status 
/////////////////////////////////////////////////////////////////////
char ISO15693_Get_Multiple_Block_Security(unsigned char flags, 
                                          unsigned char *uid, 
                                          unsigned char blnr,
                                          unsigned char nbl, 
                                          unsigned char *resplen, 
                                          unsigned char *resp);   
                                          
                                                                              