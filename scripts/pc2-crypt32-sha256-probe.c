/*
 * GameWeld PC2 Test 22 — Windows crypt32 CERT_SHA256_HASH_PROP_ID probe.
 *
 * Offline static certificate test; no external network, Steam, trainer or
 * game. Compile separately as x86_64 and i386 Windows PE executables.
 * Intended to run only inside a NEW DISPOSABLE Wine/Proton test prefix with
 * the candidate crypt32 DLL. Running against host/default Wine proves nothing
 * about the candidate DLL.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincrypt.h>
#include <stdio.h>
#include <string.h>

#ifndef CERT_SHA256_HASH_PROP_ID
#define CERT_SHA256_HASH_PROP_ID 107
#endif
#if CERT_SHA256_HASH_PROP_ID != 107
#error "Incompatible CERT_SHA256_HASH_PROP_ID; expected 107"
#endif

/* DER self-signed EC certificate, serial number 107. Fixture only. */
static const char der_hex[] =
  "308201473081eda00302010202016b300a06082a8648ce3d040302302d312b302906035504030c2247616d"
  "6557656c6420637279707433322070726f7065727479203130372074657374301e170d3230303130313030"
  "303030305a170d3335303130313030303030305a302d312b302906035504030c2247616d6557656c642063"
  "7279707433322070726f70657274792031303720746573743059301306072a8648ce3d020106082a8648ce"
  "3d03010703420004291f70d56b47d66147f7a50b1e232150e69071d194400528792a96384577dcd604"
  "4f550fef2a884ab5e7eada5baa764f2dc4aff8ed88a85b93190643afbf4f8b300a06082a8648ce3d04"
  "03020349003046022100dc27a50f2e33c31a091c2b61d518a1282a2221bececbe12a2f8525622fdbe7"
  "b10221008ed187527495afaa364fafb60889aef91953fae54518fad06fec6858cd3b2f69";

/* Independently computed from the literal DER test fixture, not Wine. */
static const char expected_sha256[] =
  "3bf3473eeac9e2dac73cc1a66982ea799389c72a5951c7d5870d89cc030e957e";
static const char expected_sha1[] =
  "d492b75fdb0fa2f9a1f7abe933527451b5b598e1";

static int nibble(char ch)
{
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}
static void digest_hex(const unsigned char *bytes, DWORD length, char *out)
{
    static const char digits[] = "0123456789abcdef";
    DWORD i;
    for (i = 0; i < length; ++i) {
        out[2*i] = digits[bytes[i] >> 4];
        out[2*i+1] = digits[bytes[i] & 0xf];
    }
    out[2*length] = '\0';
}
static int get_hash(PCCERT_CONTEXT ctx, DWORD prop, DWORD size, const char *expected,
                    const char *tag)
{
    BYTE digest[64] = {0};
    DWORD cb = 0;
    char text[129] = {0};
    if (!CertGetCertificateContextProperty(ctx, prop, NULL, &cb) || cb != size) {
        printf("GW_%s_FAIL size err=%lu len=%lu\n", tag,
               (unsigned long)GetLastError(), (unsigned long)cb);
        return 1;
    }
    if (!CertGetCertificateContextProperty(ctx, prop, digest, &cb) || cb != size) {
        printf("GW_%s_FAIL retrieval err=%lu len=%lu\n", tag,
               (unsigned long)GetLastError(), (unsigned long)cb);
        return 1;
    }
    digest_hex(digest, cb, text);
    if (strcmp(text, expected)) {
        printf("GW_%s_FAIL expected=%s actual=%s\n", tag, expected, text);
        return 1;
    }
    printf("GW_%s_OK %s\n", tag, text);
    return 0;
}

int main(void)
{
    unsigned char der[1024];
    DWORD length = 0;
    size_t i, len = strlen(der_hex);
    PCCERT_CONTEXT ctx;
    HMODULE crypt32;
    char module_name[MAX_PATH] = {0};
    BYTE bytes[32];
    CRYPT_HASH_BLOB blob;
    if (len & 1 || len / 2 > sizeof(der)) return 2;
    for (i = 0; i < len; i += 2) {
        int hi = nibble(der_hex[i]), lo = nibble(der_hex[i + 1]);
        if (hi < 0 || lo < 0) return 3;
        der[length++] = (BYTE)((hi << 4) | lo);
    }
    /* Record which Windows DLL module supplied these APIs. */
    crypt32 = GetModuleHandleA("crypt32.dll");
    if (!crypt32 || !GetModuleFileNameA(crypt32, module_name, sizeof(module_name))) {
        printf("GW_CRYPT32_MODULE_FAIL err=%lu\n", (unsigned long)GetLastError());
        return 9;
    }
    printf("GW_CRYPT32_MODULE=%s\n", module_name);
    ctx = CertCreateCertificateContext(X509_ASN_ENCODING, der, length);
    if (!ctx) {
        printf("GW_CERT_CONTEXT_FAIL err=%lu\n", (unsigned long)GetLastError());
        return 10;
    }
    if (get_hash(ctx, CERT_SHA256_HASH_PROP_ID, 32, expected_sha256, "SHA256")) {
        CertFreeCertificateContext(ctx);
        return 11;
    }
    if (get_hash(ctx, CERT_SHA1_HASH_PROP_ID, 20, expected_sha1, "SHA1")) {
        CertFreeCertificateContext(ctx);
        return 12;
    }
    /* Test the second source-patch branch: SetProperty case for ID 107.
     * Reuse the true digest, not a fabricated "pass" marker. */
    for (i = 0; i < sizeof(bytes); ++i) {
        int hi = nibble(expected_sha256[2*i]), lo = nibble(expected_sha256[2*i+1]);
        if (hi < 0 || lo < 0) return 13;
        bytes[i] = (BYTE)((hi << 4) | lo);
    }
    blob.cbData = (DWORD)sizeof(bytes);
    blob.pbData = bytes;
    if (!CertSetCertificateContextProperty(ctx, CERT_SHA256_HASH_PROP_ID, 0, &blob)) {
        printf("GW_SHA256_SET_FAIL err=%lu\n", (unsigned long)GetLastError());
        CertFreeCertificateContext(ctx);
        return 14;
    }
    if (get_hash(ctx, CERT_SHA256_HASH_PROP_ID, 32, expected_sha256, "SHA256_AFTER_SET")) {
        CertFreeCertificateContext(ctx);
        return 15;
    }
    CertFreeCertificateContext(ctx);
    printf("GW_CRYPT32_CERT_SHA256_RESULT=PASS\n");
    return 0;
}
