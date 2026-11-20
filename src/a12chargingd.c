typedef unsigned int mach_port_t;
typedef int kern_return_t;
typedef unsigned int io_object_t;
typedef io_object_t io_service_t;
typedef io_object_t io_connect_t;
typedef void* CFMutableDictionaryRef;
typedef const void* CFStringRef;
typedef const void* CFTypeRef;
typedef const void* CFBooleanRef;
typedef unsigned char uint8_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef int BOOL;

#define RTLD_NOW 2
#define NULL ((void*)0)
extern mach_port_t mach_task_self_;
#define mach_task_self() mach_task_self_

int printf(const char *fmt, ...);
void* dlopen(const char *path, int mode);
void* dlsym(void *handle, const char *symbol);
void* memset(void *s, int c, unsigned long n);
void* memcpy(void *dest, const void *src, unsigned long n);
unsigned int sleep(unsigned int seconds);

typedef CFMutableDictionaryRef (*fn_IOServiceMatching)(const char*);
typedef io_service_t (*fn_IOServiceGetMatchingService)(mach_port_t, CFMutableDictionaryRef);
typedef kern_return_t (*fn_IOServiceOpen)(io_service_t, mach_port_t, unsigned int, io_connect_t*);
typedef kern_return_t (*fn_IOServiceClose)(io_connect_t);
typedef kern_return_t (*fn_IOConnectCallStructMethod)(io_connect_t, unsigned int, const void*, unsigned long, void*, unsigned long*);
typedef kern_return_t (*fn_IOConnectCallMethod)(io_connect_t, unsigned int, const uint64_t*, unsigned int, const void*, unsigned long, uint64_t*, unsigned int*, void*, unsigned long*);
typedef kern_return_t (*fn_IORegistryEntrySetCFProperty)(io_service_t, CFStringRef, CFTypeRef);
typedef CFTypeRef (*fn_IORegistryEntryCreateCFProperty)(io_service_t, CFStringRef, void*, uint32_t);
typedef CFStringRef (*fn_CFStringCreateWithCString)(void*, const char*, unsigned int);
typedef void* (*fn_CFNumberCreate)(void*, int, const void*);
typedef BOOL (*fn_CFBooleanGetValue)(CFBooleanRef);
typedef void (*fn_CFRelease)(CFTypeRef);

static fn_IOConnectCallStructMethod f_IOConnectCallStructMethod = 0;
static fn_IOConnectCallMethod f_IOConnectCallMethod = 0;
static io_connect_t gSMC = 0;

typedef struct {
    uint32_t dataSize;
    uint32_t dataType;
    uint8_t dataAttributes;
} SMCKeyInfoData;

typedef struct {
    uint32_t key;
    struct {
        unsigned char vers[6];
        unsigned char pLimit[16];
        SMCKeyInfoData keyInfo;
        uint8_t result;
        uint8_t status;
        uint8_t data8;
        uint32_t data32;
        unsigned char bytes[120];
    } param;
} SMCParamStruct;

static kern_return_t smc_call(int index, SMCParamStruct *input, SMCParamStruct *output) {
    unsigned long inSize = sizeof(SMCParamStruct);
    unsigned long outSize = sizeof(SMCParamStruct);
    return f_IOConnectCallStructMethod(gSMC, index, input, inSize, output, &outSize);
}

static kern_return_t smc_get_keyinfo(uint32_t key, SMCKeyInfoData *keyInfo) {
    SMCParamStruct in, out;
    memset(&in, 0, sizeof(in));
    memset(&out, 0, sizeof(out));
    in.key = key;
    in.param.data8 = 9; // kSMCGetKeyInfo
    kern_return_t kr = smc_call(2, &in, &out);
    if (kr == 0 && out.param.keyInfo.dataSize == 0) return -1;
    if (kr == 0) *keyInfo = out.param.keyInfo;
    return kr;
}

static kern_return_t smc_read(uint32_t key, void *bytes, uint32_t size) {
    SMCKeyInfoData info;
    kern_return_t kr = smc_get_keyinfo(key, &info);
    if (kr != 0) return kr;

    SMCParamStruct in, out;
    memset(&in, 0, sizeof(in));
    memset(&out, 0, sizeof(out));
    in.key = key;
    in.param.keyInfo = info;
    in.param.data8 = 5; // kSMCReadKey

    kr = smc_call(2, &in, &out);
    if (kr != 0) return kr;

    uint32_t copy_size = (size < info.dataSize) ? size : info.dataSize;
    memcpy(bytes, out.param.bytes, copy_size);
    return 0;
}

static kern_return_t smc_write(uint32_t key, const void *bytes, uint32_t size) {
    SMCKeyInfoData info;
    kern_return_t kr = smc_get_keyinfo(key, &info);
    if (kr != 0) return kr;

    SMCParamStruct in, out;
    memset(&in, 0, sizeof(in));
    memset(&out, 0, sizeof(out));
    in.key = key;
    in.param.data8 = 6; // kSMCWriteKey
    in.param.keyInfo = info;
    uint32_t copy_sz = size < info.dataSize ? size : info.dataSize;
    memcpy(in.param.bytes, bytes, copy_sz);

    return smc_call(2, &in, &out);
}

static uint32_t S(const char *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) | ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}

int main(int argc, char **argv) {
    printf("[a12chargingd v4] starting clean charging daemon (NO KIOSK, NO 1%% BUG)...\n");
    void *hIOKit = dlopen("/System/Library/Frameworks/IOKit.framework/IOKit", RTLD_NOW);
    void *hCF = dlopen("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation", RTLD_NOW);
    if (!hIOKit || !hCF) return 1;

    fn_IOServiceMatching f_IOServiceMatching = (fn_IOServiceMatching)dlsym(hIOKit, "IOServiceMatching");
    fn_IOServiceGetMatchingService f_IOServiceGetMatchingService = (fn_IOServiceGetMatchingService)dlsym(hIOKit, "IOServiceGetMatchingService");
    fn_IOServiceOpen f_IOServiceOpen = (fn_IOServiceOpen)dlsym(hIOKit, "IOServiceOpen");
    fn_IOServiceClose f_IOServiceClose = (fn_IOServiceClose)dlsym(hIOKit, "IOServiceClose");
    f_IOConnectCallStructMethod = (fn_IOConnectCallStructMethod)dlsym(hIOKit, "IOConnectCallStructMethod");
    f_IOConnectCallMethod = (fn_IOConnectCallMethod)dlsym(hIOKit, "IOConnectCallMethod");
    fn_IORegistryEntrySetCFProperty f_SetCF = (fn_IORegistryEntrySetCFProperty)dlsym(hIOKit, "IORegistryEntrySetCFProperty");
    fn_IORegistryEntryCreateCFProperty f_CreateCF = (fn_IORegistryEntryCreateCFProperty)dlsym(hIOKit, "IORegistryEntryCreateCFProperty");
    fn_CFStringCreateWithCString f_Str = (fn_CFStringCreateWithCString)dlsym(hCF, "CFStringCreateWithCString");
    fn_CFNumberCreate f_Num = (fn_CFNumberCreate)dlsym(hCF, "CFNumberCreate");
    fn_CFBooleanGetValue f_BoolVal = (fn_CFBooleanGetValue)dlsym(hCF, "CFBooleanGetValue");
    fn_CFRelease f_Release = (fn_CFRelease)dlsym(hCF, "CFRelease");

    io_service_t smc_srv = f_IOServiceGetMatchingService(0, f_IOServiceMatching("AppleSMC"));
    if (!smc_srv) return 1;
    kern_return_t kr = f_IOServiceOpen(smc_srv, mach_task_self(), 0, &gSMC);
    if (kr != 0 || !gSMC) return 1;

    int zero_int = 0;
    void *val_zero = f_Num(0, 3, &zero_int);
    CFStringRef k_kiosk = f_Str(0, "KioskModeMode", 0x08000100);
    CFStringRef k_ext = f_Str(0, "ExternalConnected", 0x08000100);

    uint8_t zero8[8] = {0};
    uint8_t zero = 0;
    uint8_t one = 1;
    uint32_t chtu_full = 4350; // 4.35V = 100% full charge
    uint8_t soc_100 = 100;
    uint8_t temp_55 = 55;

    while (1) {
        // Check if charger is connected
        io_service_t batt = f_IOServiceGetMatchingService(0, f_IOServiceMatching("AppleSmartBattery"));
        BOOL is_connected = 0;
        if (batt) {
            CFTypeRef prop = f_CreateCF(batt, k_ext, NULL, 0);
            if (prop) {
                is_connected = f_BoolVal((CFBooleanRef)prop);
                f_Release(prop);
            }
            // Always ensure KioskModeMode = 0 in AppleSmartBattery
            f_SetCF(batt, k_kiosk, val_zero);
        }

        // Always ensure Kiosk keys CHKR and CHKS in SMC are 0 (NEVER 2!)
        uint8_t chkr = 0, chks = 0;
        smc_read(S("CHKR"), &chkr, 1);
        if (chkr != 0) {
            smc_write(S("CHKR"), &zero, 1);
        }
        smc_read(S("CHKS"), &chks, 1);
        if (chks != 0) {
            smc_write(S("CHKS"), &zero, 1);
        }

        if (!is_connected) {
            // UNPLUGGED: Do NOT touch charging keys or ASBM! Sleep and wait for plug.
            sleep(3);
            continue;
        }

        // --- CHARGER IS PLUGGED IN ---
        // 1. Maintain CHTU = 4350 mV
        uint32_t cur_chtu = 0;
        smc_read(S("CHTU"), &cur_chtu, 4);
        if (cur_chtu != chtu_full) {
            smc_write(S("CHTU"), &chtu_full, 4);
        }

        // 2. Maintain CC0S = 100%
        uint8_t cur_soc = 0;
        smc_read(S("CC0S"), &cur_soc, 1);
        if (cur_soc != 100) {
            smc_write(S("CC0S"), &soc_100, 1);
        }

        // 3. Maintain CC0T = 55°C
        uint8_t cur_temp = 0;
        smc_read(S("CC0T"), &cur_temp, 1);
        if (cur_temp != 55) {
            smc_write(S("CC0T"), &temp_55, 1);
        }

        // 4. Ensure CHCE = 1 (Charge Enable)
        uint8_t chce = 0;
        smc_read(S("CHCE"), &chce, 1);
        if (chce != 1) {
            smc_write(S("CHCE"), &one, 1);
        }

        // 5. Ensure Inhibit keys are 0
        uint8_t ch0i = 0;
        smc_read(S("CH0I"), &ch0i, 1);
        if (ch0i != 0) {
            smc_write(S("CH0I"), &zero, 1);
            smc_write(S("CH0K"), &zero, 1);
            smc_write(S("CH0J"), &zero, 1);
            smc_write(S("CHIE"), &zero, 1);
        }

        // 6. Check and clear CHNC (NotChargingReason) if set
        uint8_t chnc[8] = {0};
        smc_read(S("CHNC"), chnc, 8);
        if (chnc[0] || chnc[1] || chnc[2] || chnc[3] || chnc[4] || chnc[5] || chnc[6] || chnc[7]) {
            smc_write(S("CHNC"), zero8, 8);
            smc_write(S("CH0I"), &zero, 1);
            smc_write(S("CH0C"), &zero, 1);
            smc_write(S("CH0B"), &zero, 1);
            smc_write(S("CH0K"), &zero, 1);
            smc_write(S("CH0J"), &zero, 1);
            smc_write(S("CHST"), &zero, 1);
            smc_write(S("CHSC"), &zero, 1);

            // Call ASBM with 0 ONLY (NEVER arg=2!)
            io_service_t asbm_srv = f_IOServiceGetMatchingService(0, f_IOServiceMatching("AppleSmartBatteryManager"));
            if (asbm_srv) {
                io_connect_t asbm_conn = 0;
                if (f_IOServiceOpen(asbm_srv, mach_task_self(), 0, &asbm_conn) == 0 && asbm_conn) {
                    uint64_t in_scalar = 0;
                    uint64_t out_scalar[4] = {0};
                    uint32_t out_count = 4;
                    // Selector 0 (arg=0): clear inhibit
                    f_IOConnectCallMethod(asbm_conn, 0, &in_scalar, 1, 0, 0, out_scalar, &out_count, 0, 0);
                    // Selector 5 (arg=0)
                    f_IOConnectCallMethod(asbm_conn, 5, &in_scalar, 1, 0, 0, out_scalar, &out_count, 0, 0);
                    // Selector 1 (poll)
                    f_IOConnectCallMethod(asbm_conn, 1, 0, 0, 0, 0, out_scalar, &out_count, 0, 0);
                    // Selector 6
                    f_IOConnectCallMethod(asbm_conn, 6, 0, 0, 0, 0, out_scalar, &out_count, 0, 0);
                    f_IOServiceClose(asbm_conn);
                }
            }
        }

        sleep(2);
    }

    return 0;
}
