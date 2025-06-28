import requests

# Token de canvas
token = '14476~9kJPt8CrHEyE7xt7W9DwMrHVhUAT4FVL7PUrxTKUDAf7KPPrwRDVxmTPmJVuzKaU'

headers = {'Authorization': f'Bearer {token}'}

# URL de api
response = requests.get('https://ufv.instructure.com/api/v1/users/self', headers=headers)


print("Código de respuesta:", response.status_code)
print("Respuesta:", response.json())
