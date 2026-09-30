/*
 * blr_redirect — minimal libmain.so replacement for Battlelands Royale 2.9.6 (arm64-v8a).
 *
 * Reproduces only the Photon redirect of Battlelands Reborn (eu.c / detour.c / natif.c):
 *
 *   JNI_OnLoad
 *     -> dlopen(libmain_orig.so) + call its JNI_OnLoad   (normal Unity boot)
 *     -> background thread:
 *          wait for libil2cpp.so + il2cpp_get_corlib() != NULL
 *          resolve PhotonNetwork / NetworkingPeer / FuturePlay.GameSettings
 *          inline-hook PhotonNetwork.ConnectToRegion(CloudRegionCode, string)
 *          inline-hook NetworkingPeer.ConnectToRegionMaster(CloudRegionCode)
 *
 *   hook -> PhotonNetwork.SwitchToProtocol(Tcp)
 *        -> PhotonNetwork.ConnectToMaster(BLR_PHOTON_HOST, BLR_PHOTON_PORT,
 *                                         PhotonServerSettings.AppID, gameVersion)
 *
 * Nothing else from Reborn (UI, clans, maps, rules, HTTP side-channel, reachability probe).
 * Freestanding: no libc headers, so it can be syntax-checked without the NDK.
 */

typedef unsigned long size_t;
typedef unsigned long uintptr_t;
typedef unsigned long long uint64_t;
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;
typedef int int32_t;

#ifndef BLR_PHOTON_HOST
#define BLR_PHOTON_HOST "127.0.0.1"
#endif
#ifndef BLR_PHOTON_PORT
#define BLR_PHOTON_PORT 4530          /* Photon Server default TCP master port */
#endif
#ifndef BLR_REDIRECT_ALL_REGIONS
#define BLR_REDIRECT_ALL_REGIONS 1    /* Reborn only redirects CloudRegionCode.eu (0) */
#endif
#ifndef BLR_DRY_RUN
#define BLR_DRY_RUN 0                 /* 1 = log AppID/version/region, then call original */
#endif

#define TAG "BLRRedirect"
#define RTLD_NOW 2
#define RTLD_NOLOAD 4
#define PROT_RWX 7
#define PROT_RX 5
#define MAP_PRIVATE_ANON 0x22
#define SC_PAGESIZE 39
#define CONNECTION_PROTOCOL_TCP 1     /* ExitGames.Client.Photon.ConnectionProtocol.Tcp */
#define CLOUD_REGION_EU 0             /* CloudRegionCode.eu */

extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);
extern int __android_log_print(int, const char *, const char *, ...);
extern void *mmap(void *, size_t, int, int, int, long);
extern int mprotect(void *, size_t, int);
extern long sysconf(int);
extern int pthread_create(long *, const void *, void *(*)(void *), void *);
extern int pthread_detach(long);
extern int usleep(unsigned);
extern void *memcpy(void *, const void *, size_t);

#define LOGI(...) __android_log_print(4, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(6, TAG, __VA_ARGS__)

/* Same as compiler-rt __clear_cache on AArch64 (kept inline: no NDK runtime needed). */
static void flush_code(void *start, void *end)
{
    uint64_t ctr;
    __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
    uintptr_t dline = 4u << ((ctr >> 16) & 15), iline = 4u << (ctr & 15);
    for (uintptr_t p = (uintptr_t)start & ~(dline - 1); p < (uintptr_t)end; p += dline)
        __asm__ volatile("dc cvau, %0" :: "r"(p) : "memory");
    __asm__ volatile("dsb ish" ::: "memory");
    for (uintptr_t p = (uintptr_t)start & ~(iline - 1); p < (uintptr_t)end; p += iline)
        __asm__ volatile("ic ivau, %0" :: "r"(p) : "memory");
    __asm__ volatile("dsb ish\n\tisb" ::: "memory");
}

/* ---- IL2CPP API (resolved at runtime from libil2cpp.so) ---- */

typedef struct { void *methodPointer; } MethodInfo;   /* methodPointer is the first field */

static void *(*il2cpp_get_corlib)(void);
static void *(*il2cpp_domain_get)(void);
static void *(*il2cpp_thread_attach)(void *);
static void **(*il2cpp_domain_get_assemblies)(void *, size_t *);
static void *(*il2cpp_assembly_get_image)(void *);
static void *(*il2cpp_class_from_name)(void *, const char *, const char *);
static MethodInfo *(*il2cpp_class_get_method_from_name)(void *, const char *, int);
static void *(*il2cpp_class_get_field_from_name)(void *, const char *);
static void (*il2cpp_field_static_get_value)(void *, void *);
static size_t (*il2cpp_field_get_offset)(void *);
static void *(*il2cpp_object_get_class)(void *);
static void *(*il2cpp_runtime_invoke)(MethodInfo *, void *, void **, void **);
static void *(*il2cpp_string_new)(const char *);
static uint16_t *(*il2cpp_string_chars)(void *);
static int32_t (*il2cpp_string_length)(void *);

#define RESOLVE(h, name) \
    if (!(*(void **)&name = dlsym(h, #name))) { LOGE("export manquant : %s", #name); return 0; }

static int resolve_il2cpp(void *h)
{
    RESOLVE(h, il2cpp_get_corlib);
    RESOLVE(h, il2cpp_domain_get);
    RESOLVE(h, il2cpp_thread_attach);
    RESOLVE(h, il2cpp_domain_get_assemblies);
    RESOLVE(h, il2cpp_assembly_get_image);
    RESOLVE(h, il2cpp_class_from_name);
    RESOLVE(h, il2cpp_class_get_method_from_name);
    RESOLVE(h, il2cpp_class_get_field_from_name);
    RESOLVE(h, il2cpp_field_static_get_value);
    RESOLVE(h, il2cpp_field_get_offset);
    RESOLVE(h, il2cpp_object_get_class);
    RESOLVE(h, il2cpp_runtime_invoke);
    RESOLVE(h, il2cpp_string_new);
    RESOLVE(h, il2cpp_string_chars);
    RESOLVE(h, il2cpp_string_length);
    return 1;
}

static void *find_class(const char *ns, const char *name)
{
    size_t n = 0;
    void **assemblies = il2cpp_domain_get_assemblies(il2cpp_domain_get(), &n);
    for (size_t i = 0; i < n; i++) {
        void *k = il2cpp_class_from_name(il2cpp_assembly_get_image(assemblies[i]), ns, name);
        if (k) return k;
    }
    LOGE("classe introuvable : %s.%s", ns, name);
    return 0;
}

static void *invoke(MethodInfo *m, void *obj, void **args)
{
    void *exc = 0;
    void *ret = il2cpp_runtime_invoke(m, obj, args, &exc);
    if (exc) { LOGE("exception pendant l'appel IL2CPP"); return 0; }
    return ret;
}

static void *object_field(void *obj, const char *name)
{
    void *f = obj ? il2cpp_class_get_field_from_name(il2cpp_object_get_class(obj), name) : 0;
    return f ? *(void **)((char *)obj + il2cpp_field_get_offset(f)) : 0;
}

static void to_ascii(void *str, char *out, int cap)
{
    int n = 0;
    if (str) {
        uint16_t *c = il2cpp_string_chars(str);
        int len = il2cpp_string_length(str);
        for (; n < len && n < cap - 1; n++) out[n] = c[n] < 0x80 ? (char)c[n] : '?';
    }
    out[n] = 0;
}

/* ---- Inline hook (same scheme as Reborn detour.c) ----
 * target[0..3] <- LDR X16,#8 ; BR X16 ; .quad replacement
 * trampoline   <- original 4 instructions ; LDR X16,#8 ; BR X16 ; .quad target+16
 * The 4 relocated instructions must not be PC-relative. */

static int pc_relative(uint32_t op)
{
    return (op & 0x1f000000) == 0x10000000     /* ADR / ADRP */
        || (op & 0x7c000000) == 0x14000000     /* B / BL */
        || (op & 0x7e000000) == 0x34000000     /* CBZ / CBNZ */
        || (op & 0x7e000000) == 0x36000000     /* TBZ / TBNZ */
        || (op & 0xff000010) == 0x54000000     /* B.cond */
        || (op & 0x3b000000) == 0x18000000;    /* LDR (literal) */
}

static void *inline_hook(void *target, void *replacement, const char *what)
{
    uint32_t *t = target;
    if (!t) { LOGE("hook : %s introuvable", what); return 0; }
    for (int i = 0; i < 4; i++)
        if (pc_relative(t[i])) { LOGE("hook : prologue de %s non deplacable (%08x)", what, t[i]); return 0; }

    uint32_t *tramp = mmap(0, 32, PROT_RWX, MAP_PRIVATE_ANON, -1, 0);
    if (tramp == (void *)-1) { LOGE("hook : mmap refuse pour %s", what); return 0; }
    uint32_t jump[2] = { 0x58000050, 0xd61f0200 };            /* ldr x16, #8 ; br x16 */
    uint64_t back = (uint64_t)(uintptr_t)(t + 4);
    memcpy(tramp, t, 16);
    memcpy(tramp + 4, jump, 8);
    memcpy(tramp + 6, &back, 8);
    flush_code(tramp, tramp + 8);

    uintptr_t page = (uintptr_t)sysconf(SC_PAGESIZE);
    uintptr_t start = (uintptr_t)t & ~(page - 1);
    size_t len = (((uintptr_t)t + 16 + page - 1) & ~(page - 1)) - start;
    if (mprotect((void *)start, len, PROT_RWX)) { LOGE("hook : mprotect refuse pour %s", what); return 0; }
    uint64_t dst = (uint64_t)(uintptr_t)replacement;
    memcpy(t, jump, 8);
    memcpy(t + 2, &dst, 8);
    flush_code(t, t + 4);
    mprotect((void *)start, len, PROT_RX);

    LOGI("[BLR] %s hook installed (trampoline %p)", what, tramp);
    return tramp;
}

/* ---- Photon redirect ---- */

static void *k_photon_network;
static MethodInfo *m_connect_to_master;   /* PhotonNetwork.ConnectToMaster(string,int,string,string) */
static MethodInfo *m_switch_protocol;     /* PhotonNetwork.SwitchToProtocol(ConnectionProtocol) */
static MethodInfo *m_game_version;        /* FuturePlay.GameSettings.get_PhotonGameVersion() */

typedef uint8_t (*connect_region_fn)(int32_t region, void *game_version, const MethodInfo *m);
typedef uint8_t (*connect_region_master_fn)(void *self, int32_t region, const MethodInfo *m);
static connect_region_fn connect_region_orig;
static connect_region_master_fn connect_region_master_orig;

static int should_redirect(int32_t region)
{
    return m_connect_to_master && m_switch_protocol
        && (BLR_REDIRECT_ALL_REGIONS || region == CLOUD_REGION_EU);
}

/* Equivalent of Reborn vers_eu(): returns ConnectToMaster's bool. */
static uint8_t redirect(int32_t region, void *game_version)
{
    void *settings = 0;
    void *f = il2cpp_class_get_field_from_name(k_photon_network, "PhotonServerSettings");
    if (f) il2cpp_field_static_get_value(f, &settings);
    void *app_id = object_field(settings, "AppID");

    if (!game_version && m_game_version) game_version = invoke(m_game_version, 0, 0);
    if (!app_id) app_id = il2cpp_string_new("");
    if (!game_version) game_version = il2cpp_string_new("");

    char app[80], ver[64];
    to_ascii(app_id, app, sizeof app);
    to_ascii(game_version, ver, sizeof ver);
    LOGI("[BLR] %s region %d -> %s:%d (TCP) AppID=%s PhotonGameVersion=%s",
         BLR_DRY_RUN ? "DRY RUN, would redirect" : "redirect", region, BLR_PHOTON_HOST,
         BLR_PHOTON_PORT, app, ver);
    if (BLR_DRY_RUN) return 2;   /* sentinel: caller falls through to original */

    int32_t protocol = CONNECTION_PROTOCOL_TCP;
    void *proto_args[1] = { &protocol };
    invoke(m_switch_protocol, 0, proto_args);

    int32_t port = BLR_PHOTON_PORT;
    void *args[4] = { il2cpp_string_new(BLR_PHOTON_HOST), &port, app_id, game_version };
    void *boxed = invoke(m_connect_to_master, 0, args);
    uint8_t ok = boxed ? *((uint8_t *)boxed + 0x10) : 0;   /* unbox System.Boolean */
    LOGI("[BLR] ConnectToMaster -> %s", ok ? "true" : "false");
    return ok;
}

static uint8_t connect_region_hook(int32_t region, void *game_version, const MethodInfo *m)
{
    LOGI("[BLR] ConnectToRegion invoked (region %d)", region);
    if (should_redirect(region)) {
        uint8_t r = redirect(region, game_version);
        if (r != 2) return r;
    }
    return connect_region_orig(region, game_version, m);
}

static uint8_t connect_region_master_hook(void *self, int32_t region, const MethodInfo *m)
{
    LOGI("[BLR] NetworkingPeer.ConnectToRegionMaster invoked (region %d)", region);
    if (should_redirect(region)) {
        uint8_t r = redirect(region, 0);
        if (r != 2) return r;
    }
    return connect_region_master_orig(self, region, m);
}

static void install_photon_redirect(void)
{
    k_photon_network = find_class("", "PhotonNetwork");
    void *k_peer = find_class("", "NetworkingPeer");
    void *k_settings = find_class("FuturePlay", "GameSettings");
    if (!k_photon_network || !k_peer) { LOGE("PUN introuvable, pas de redirection"); return; }
    LOGI("[BLR] PhotonNetwork resolved (PhotonNetwork %p, NetworkingPeer %p, GameSettings %p)",
         k_photon_network, k_peer, k_settings);

    m_connect_to_master = il2cpp_class_get_method_from_name(k_photon_network, "ConnectToMaster", 4);
    m_switch_protocol = il2cpp_class_get_method_from_name(k_photon_network, "SwitchToProtocol", 1);
    if (k_settings) m_game_version = il2cpp_class_get_method_from_name(k_settings, "get_PhotonGameVersion", 0);
    if (!m_connect_to_master || !m_switch_protocol) {
        LOGE("ConnectToMaster ou SwitchToProtocol introuvable, pas de redirection");
        return;
    }

    MethodInfo *m_region = il2cpp_class_get_method_from_name(k_photon_network, "ConnectToRegion", 2);
    MethodInfo *m_region_master = il2cpp_class_get_method_from_name(k_peer, "ConnectToRegionMaster", 1);
    connect_region_orig = inline_hook(m_region ? m_region->methodPointer : 0,
                                      connect_region_hook, "PhotonNetwork.ConnectToRegion");
    connect_region_master_orig = inline_hook(m_region_master ? m_region_master->methodPointer : 0,
                                             connect_region_master_hook, "NetworkingPeer.ConnectToRegionMaster");
}

/* ---- Boot (equivalent of Reborn natif.c, without AudioManager/UI) ---- */

static void *wait_il2cpp(void *arg)
{
    (void)arg;
    void *h = 0;
    for (int i = 0; i < 1200 && !(h = dlopen("libil2cpp.so", RTLD_NOW | RTLD_NOLOAD)); i++) usleep(100000);
    if (!h || !resolve_il2cpp(h)) { LOGE("libil2cpp introuvable"); return 0; }

    int i = 0;
    for (; i < 1200 && !il2cpp_get_corlib(); i++) usleep(100000);
    if (i == 1200) { LOGE("VM IL2CPP jamais initialisee"); return 0; }
    usleep(500000);
    il2cpp_thread_attach(il2cpp_domain_get());
    LOGI("[BLR] IL2CPP ready");

    install_photon_redirect();
    return 0;
}

__attribute__((visibility("default"))) int JNI_OnLoad(void *vm, void *reserved)
{
    int version = 0x10006;   /* JNI_VERSION_1_6 */
    LOGI("[BLR] libmain loaded (Photon %s:%d, dry run %d)", BLR_PHOTON_HOST, BLR_PHOTON_PORT, BLR_DRY_RUN);
    void *orig = dlopen("libmain_orig.so", RTLD_NOW);
    if (!orig) {
        LOGE("libmain_orig.so : %s", dlerror());
        return version;
    }
    int (*orig_onload)(void *, void *) = (int (*)(void *, void *))dlsym(orig, "JNI_OnLoad");
    LOGI("[BLR] libmain_orig loaded, JNI_OnLoad %p", (void *)orig_onload);
    if (orig_onload) version = orig_onload(vm, reserved);

    long thread;
    if (!pthread_create(&thread, 0, wait_il2cpp, 0)) pthread_detach(thread);
    LOGI("[BLR] original JNI_OnLoad returned %x, waiting for IL2CPP", version);
    return version;
}
