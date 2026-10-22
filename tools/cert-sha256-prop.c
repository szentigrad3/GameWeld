#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wincrypt.h>
#include <wintrust.h>
#include <softpub.h>
#include <stdio.h>

#ifndef CERT_SHA256_HASH_PROP_ID
#define CERT_SHA256_HASH_PROP_ID 107
#endif

static void print_hex(const BYTE *p, DWORD n)
{
    DWORD i;
    for (i = 0; i < n; ++i) printf("%02x", p[i]);
    putchar('\n');
}

int wmain(int argc, wchar_t **argv)
{
    WINTRUST_FILE_INFO file_info = {0};
    WINTRUST_DATA trust_data = {0};
    GUID policy = WINTRUST_ACTION_GENERIC_VERIFY_V2;
    CRYPT_PROVIDER_DATA *provider;
    CRYPT_PROVIDER_SGNR *signer;
    PCCERT_CONTEXT cert;
    LONG trust_status;
    DWORD size = 0;
    BYTE hash[32];
    BOOL ok;

    if (argc != 2)
    {
        fwprintf(stderr, L"usage: cert-sha256-prop.exe <signed-pe>\n");
        return 2;
    }

    file_info.cbStruct = sizeof(file_info);
    file_info.pcwszFilePath = argv[1];

    trust_data.cbStruct = sizeof(trust_data);
    trust_data.dwUIChoice = WTD_UI_NONE;
    trust_data.fdwRevocationChecks = WTD_REVOKE_NONE;
    trust_data.dwUnionChoice = WTD_CHOICE_FILE;
    trust_data.pFile = &file_info;
    trust_data.dwStateAction = WTD_STATEACTION_VERIFY;
    trust_data.dwProvFlags = WTD_CACHE_ONLY_URL_RETRIEVAL | WTD_REVOCATION_CHECK_NONE;

    trust_status = WinVerifyTrust(NULL, &policy, &trust_data);
    printf("WinVerifyTrust=0x%08lx\n", (unsigned long)trust_status);

    provider = WTHelperProvDataFromStateData(trust_data.hWVTStateData);
    signer = provider ? WTHelperGetProvSignerFromChain(provider, 0, FALSE, 0) : NULL;
    cert = (signer && signer->csCertChain) ? signer->pasCertChain[0].pCert : NULL;

    if (!cert)
    {
        printf("signer_certificate=unavailable\n");
        trust_data.dwStateAction = WTD_STATEACTION_CLOSE;
        WinVerifyTrust(NULL, &policy, &trust_data);
        return 3;
    }

    SetLastError(ERROR_SUCCESS);
    ok = CertGetCertificateContextProperty(cert, CERT_SHA256_HASH_PROP_ID, NULL, &size);
    printf("CERT_SHA256_HASH_PROP_ID.size.ok=%d size=%lu last_error=0x%08lx\n",
           ok, (unsigned long)size, (unsigned long)GetLastError());

    if (ok && size == sizeof(hash))
    {
        SetLastError(ERROR_SUCCESS);
        ok = CertGetCertificateContextProperty(cert, CERT_SHA256_HASH_PROP_ID, hash, &size);
        printf("CERT_SHA256_HASH_PROP_ID.value.ok=%d size=%lu last_error=0x%08lx\n",
               ok, (unsigned long)size, (unsigned long)GetLastError());
        if (ok) print_hex(hash, size);
    }

    trust_data.dwStateAction = WTD_STATEACTION_CLOSE;
    WinVerifyTrust(NULL, &policy, &trust_data);
    return (trust_status == ERROR_SUCCESS && ok) ? 0 : 1;
}
