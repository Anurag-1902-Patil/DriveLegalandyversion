from rag.jurisdiction import get_fine_lookup_scopes
from rag import challan

print('scopes India:', get_fine_lookup_scopes('', '', 'India'))
print('scopes Germany:', get_fine_lookup_scopes('', '', 'Germany'))
print('scopes Pune,India:', get_fine_lookup_scopes('Pune', 'Maharashtra', 'India'))
print('scopes Pune,Germany:', get_fine_lookup_scopes('Pune', 'Maharashtra', 'Germany'))

print('lookup drunk driving (no loc):', challan.lookup_fine('drunk driving penalty', city='', state=''))
print('lookup red light Germany:', challan.lookup_fine('red light fine', city='', state='', country='Germany'))
print('lookup red light no country:', challan.lookup_fine('red light fine', city='', state='', country=''))
