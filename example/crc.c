#define CRC_TABLE_SIZE    256
unsigned long calcCRC( const uint8_t *mem, signed long size, unsigned long CRC, unsigned long *table ) 
{
    CRC = ~CRC;

    while(size--)
    {
        CRC = table[(CRC ^ *(mem++)) & 0xFF] ^ (CRC >> 8);
    }

    return ~CRC;
}

void makeCRCtable( unsigned long *table, unsigned long id  ) 
{
    unsigned long i, j, k;

    for( i = 0; i < CRC_TABLE_SIZE; ++i )
    {
        k = i;
        for( j = 0; j < 8; ++j ) 
        {
            if (k & 1)
            {
                k = (k >> 1) ^ id;
            }
            else
            {
                k >>= 1;
            }
        }
        table[i] = k;
    }
}

unsigned long eeGetFileCRC( const char * fileName ) 
{
    uint8_t buf [32768];
    unsigned long table[CRC_TABLE_SIZE];
    unsigned long CRC = 0;
    size_t len;

    dbg(MODEM_OFF, (char *)"file name: %s\r\n", fileName );

    FILE* s = fopen( fileName, "r" );

    if(s == NULL)
    {
        dbg(MODEM_OFF, (char *)"%s open fail\r\n", fileName);
        return false;
    }

    makeCRCtable(table, 0xEDB88320);

    while ( (len = fread(buf, 1, sizeof(buf), s)) != 0 )
    {
        //dbg(MODEM_OFF, (char *)"--> len: %d\r\n", len);
        
        CRC = calcCRC( buf, (unsigned long) len, CRC, table );
    }

    dbg(MODEM_NRM, (char *)"%s : %x\r\n", __func__, CRC );
    return CRC;
}

uint8_t fnCompareFileCrc(void)
{
    int res = true;
    unsigned long file_crc = 0;
    char crc_tmp[128];
    memset(crc_tmp, 0, 128);

    if(modemFotaDb.dev_code == PACKAGE_T_CP970)
    {
        if(modemFotaDb.total_crc != 0)
        {
            sprintf(&crc_tmp[0], "/root/%s.dat", modemFotaDb.main_filename);
            file_crc = eeGetFileCRC(crc_tmp);
            if(file_crc != 0)
            {
                dbg(MODEM_NRM, (char *)"read crc: %x   receive crc: %x\r\n", file_crc, modemFotaDb.total_crc);
                if(file_crc != modemFotaDb.total_crc)
                {
                    dbg(MODEM_NRM, (char *)"File CRC Fail\r\n");
                    res = false;
                }
                else
                    dbg(MODEM_NRM, (char *)"File CRC OK\r\n");
            }
        }
    }
    else if(modemFotaDb.dev_code == PACKAGE_T_INF267RS)
    {
        if(modemFotaDb.total_crc != 0)
        {
            sprintf(&crc_tmp[0], "/root/%s.dat", modemFotaDb.wire_filename);
            file_crc = eeGetFileCRC(crc_tmp);
            if(file_crc != 0)
            {
                dbg(MODEM_NRM, (char *)"read crc: %x   receive crc: %x\r\n", file_crc, modemFotaDb.total_crc);
                if(file_crc != modemFotaDb.total_crc)
                {
                    dbg(MODEM_NRM, (char *)"File CRC Fail\r\n");
                    res = false;
                }
                else
                    dbg(MODEM_NRM, (char *)"File CRC OK\r\n");
            }
        }
    }
    else if(modemFotaDb.dev_code == PACKAGE_T_INF260Z)
    {
        if(modemFotaDb.total_crc != 0)
        {
            sprintf(&crc_tmp[0], "/root/%s.dat", modemFotaDb.wireless_filename);
            file_crc = eeGetFileCRC(crc_tmp);
            if(file_crc != 0)
            {
                dbg(MODEM_NRM, (char *)"read crc: %x   receive crc: %x\r\n", file_crc, modemFotaDb.total_crc);
                if(file_crc != modemFotaDb.total_crc)
                {
                    dbg(MODEM_NRM, (char *)"File CRC Fail\r\n");
                    res = false;
                }
                else
                    dbg(MODEM_NRM, (char *)"File CRC OK\r\n");
            }
        }
    }

    return res;
}
