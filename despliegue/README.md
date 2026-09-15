\# Despliegue en AWS EC2



\## Recursos utilizados

\- Instancia EC2: t3.micro, Amazon Linux 2023

\- IP pública: 54.205.8.42

\- Puertos abiertos: 22 (SSH) y 8050 (Dash), origen 0.0.0.0/0



\## Pasos para replicar el despliegue



1\. Lanzar una instancia EC2 (t3.micro, Amazon Linux) y crear/descargar un par de claves .pem.

2\. En el grupo de seguridad de la instancia, agregar una regla de entrada TCP personalizado, puerto 8050, origen Anywhere-IPv4.

3\. Conectarse por SSH:

&#x20;  ssh -i llave.pem ec2-user@<IP\_PUBLICA>

4\. Instalar dependencias en la instancia:

&#x20;  sudo yum update -y

&#x20;  sudo yum install python3-pip -y

&#x20;  pip3 install dash plotly pandas pyarrow gunicorn

5\. Desde el computador local, subir los archivos del tablero (sin el CSV original):

&#x20;  scp -i llave.pem app.py datos\_extensiones.parquet datos\_concentracion.parquet ec2-user@<IP\_PUBLICA>:/home/ec2-user

6\. En la instancia, editar la última línea de app.py para que escuche en todas las interfaces:

&#x20;  nano app.py

&#x20;  # cambiar: app.run(debug=True)

&#x20;  # por:     app.run(host="0.0.0.0", debug=True)

7\. Lanzar la app de forma persistente:

&#x20;  nohup gunicorn -b 0.0.0.0:8050 app:server \&

8\. Verificar en el navegador:

&#x20;  http://<IP\_PUBLICA>:8050

9\. Al finalizar, terminar la instancia desde la consola EC2 (Actions = Terminate)



\## Archivos incluidos

\- `app.py`: aplicación Dash con las dos preguntas de negocio.

\- `datos\_extensiones.parquet`, `datos\_concentracion.parquet`: datos procesados que consume la app.

