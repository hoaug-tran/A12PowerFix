typedef void* id;
typedef void* SEL;
typedef void* IMP;
typedef void* Class;
typedef void* Method;
typedef int BOOL;

#define NO 0
#define YES 1
#define NULL ((void*)0)
#define RTLD_DEFAULT ((void*)-2)

void* dlsym(void *handle, const char *symbol);

typedef Class (*fn_objc_getClass)(const char *name);
typedef SEL (*fn_sel_registerName)(const char *str);
typedef IMP (*fn_class_replaceMethod)(Class cls, SEL name, IMP imp, const char *types);
typedef id (*fn_objc_msgSend)(id self, SEL op, ...);

static fn_objc_getClass f_objc_getClass = 0;
static fn_sel_registerName f_sel_registerName = 0;
static fn_class_replaceMethod f_class_replaceMethod = 0;
static fn_objc_msgSend f_objc_msgSend = 0;

static BOOL hook_NO(id self, SEL _cmd) {
    return NO;
}

static int hook_zero(id self, SEL _cmd) {
    return 0;
}

static void hook_void(id self, SEL _cmd) {
}

static void hook_void_arg(id self, SEL _cmd, id arg) {
}

static void hook_viewWillAppear(id self, SEL _cmd, BOOL animated) {
    if (f_sel_registerName && f_objc_msgSend) {
        SEL sel_dismiss = f_sel_registerName("dismissViewControllerAnimated:completion:");
        ((void (*)(id, SEL, BOOL, void*))f_objc_msgSend)(self, sel_dismiss, NO, NULL);
    }
}

__attribute__((constructor))
static void init_kill_thermal_alert(void) {
    f_objc_getClass = (fn_objc_getClass)dlsym(RTLD_DEFAULT, "objc_getClass");
    f_sel_registerName = (fn_sel_registerName)dlsym(RTLD_DEFAULT, "sel_registerName");
    f_class_replaceMethod = (fn_class_replaceMethod)dlsym(RTLD_DEFAULT, "class_replaceMethod");
    f_objc_msgSend = (fn_objc_msgSend)dlsym(RTLD_DEFAULT, "objc_msgSend");

    if (!f_objc_getClass || !f_sel_registerName || !f_class_replaceMethod) return;

    // 1. Hook SBThermalController to never report thermal trap or emergency
    Class tcCls = f_objc_getClass("SBThermalController");
    if (tcCls) {
        f_class_replaceMethod(tcCls, f_sel_registerName("isInThermalTrap"), (IMP)hook_NO, "c@:");
        f_class_replaceMethod(tcCls, f_sel_registerName("isThermalBlocked"), (IMP)hook_NO, "c@:");
        f_class_replaceMethod(tcCls, f_sel_registerName("level"), (IMP)hook_zero, "i@:");
        f_class_replaceMethod(tcCls, f_sel_registerName("showThermalAlertIfNecessary"), (IMP)hook_void, "v@:");
        f_class_replaceMethod(tcCls, f_sel_registerName("_updateThermalTrapState"), (IMP)hook_void, "v@:");
        f_class_replaceMethod(tcCls, f_sel_registerName("_setThermalEmergencyAlertItem:"), (IMP)hook_void_arg, "v@:@");
    }

    // 2. Hook SBThermalEmergencyAlertItem to prevent display
    Class alertCls = f_objc_getClass("SBThermalEmergencyAlertItem");
    if (alertCls) {
        f_class_replaceMethod(alertCls, f_sel_registerName("configure:requirePasscodeForActions:"), (IMP)hook_void_arg, "v@:cc");
        f_class_replaceMethod(alertCls, f_sel_registerName("shouldShowInEmergencyCall"), (IMP)hook_NO, "c@:");
    }

    // 3. Hook SBTemperatureWarningViewController
    Class warnCls = f_objc_getClass("SBTemperatureWarningViewController");
    if (warnCls) {
        f_class_replaceMethod(warnCls, f_sel_registerName("viewWillAppear:"), (IMP)hook_viewWillAppear, "v@:c");
    }
}
