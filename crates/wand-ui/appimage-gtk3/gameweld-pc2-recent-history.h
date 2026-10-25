#ifndef GAMEWELD_PC2_RECENT_HISTORY_H
#define GAMEWELD_PC2_RECENT_HISTORY_H

/* Bounded, source-independent list of recently SELECTED game identities.
 * No playtime or game-running claim is inferred from a selection.
 * This header is GTK-free so order/deduplication can be regression-tested. */
#include <string.h>
#define GAMEWELD_PC2_RECENT_COUNT 6
#define GAMEWELD_PC2_RECENT_KEY_SIZE 320

typedef struct {
    char keys[GAMEWELD_PC2_RECENT_COUNT][GAMEWELD_PC2_RECENT_KEY_SIZE];
    int count;
} GameWeldPC2RecentHistory;

static int gameweld_pc2_recent_key_ok(const char *key) {
    if(!key || !*key) return 0;
    size_t n=strnlen(key,GAMEWELD_PC2_RECENT_KEY_SIZE);
    if(n==0 || n>=GAMEWELD_PC2_RECENT_KEY_SIZE) return 0;
    for(size_t i=0;i<n;i++)
        if((unsigned char)key[i]<32 || (unsigned char)key[i]==127) return 0;
    return 1;
}
static int gameweld_pc2_recent_push(GameWeldPC2RecentHistory *history,
                                   const char *key) {
    if(!history || !gameweld_pc2_recent_key_ok(key)) return 0;
    if(history->count<0 || history->count>GAMEWELD_PC2_RECENT_COUNT)
        history->count=0;
    int old=-1;
    for(int i=0;i<history->count;i++)
        if(!strcmp(history->keys[i],key)){old=i;break;}
    if(old==0)return 0;
    if(old>0) {
        for(int i=old;i>0;i--)
            memcpy(history->keys[i],history->keys[i-1],GAMEWELD_PC2_RECENT_KEY_SIZE);
    }else{
        int last=history->count<GAMEWELD_PC2_RECENT_COUNT?
                 history->count++:GAMEWELD_PC2_RECENT_COUNT-1;
        for(int i=last;i>0;i--)
            memcpy(history->keys[i],history->keys[i-1],GAMEWELD_PC2_RECENT_KEY_SIZE);
    }
    memset(history->keys[0],0,GAMEWELD_PC2_RECENT_KEY_SIZE);
    memcpy(history->keys[0],key,strlen(key));
    return 1;
}
#endif
