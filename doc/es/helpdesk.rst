=============
Soporte - CRM
=============

La relación con el cliente conocido como CRM (customer relatioship management)
permite gestionar la información de los terceros o contactos de empresas o otros
tipos de organización.

En el CRM se registra la información de los clientes/contactos y sus interrelaciones.

El CRM lo hemos rellamado "soporte". Con él podrá dar información de sus servicios o
incidencias y estar relacionados con distintas áreas de su ERP.

Cada comunicación con el cliente lo llamamos "tique" y cada tique dispone de
las conversaciones.

.. inheritref:: helpdesk/helpdesk:section:estados_del_tique

Estados del tique
=================

 * Borrador
 * Abrir
 * Pendiente
 * Cerrar

En el historial del tique se va anotando el cambio de los estados de la conversación
y del usuario, como la fecha de realización.

.. inheritref:: helpdesk/helpdesk:section:todos_los_tique

Todos los tique
===============

Si accedemos a soportes o por secciones, sólo nos mostrará los tiques que esten asignados al
empleado del nuestro usuario (sólo veremos nuestros tiques).

Para ver todos los tiques (sin la condición de empleado) deberá acceder al menú "Todos los soportes".
Para acceder a este menú el usuario debe ser del grupo "Gestor de soporte".

.. inheritref:: helpdesk/helpdesk:section:secciones

Secciones
=========

Se dispone del menú |menu_helpdesk| para acceder a todos los soportes. 

.. |menu_helpdesk| tryref:: getmail.menu_getmail_server_form/complete_name

A continuación disponéis de las diferentes secciones sobre
la comunicación con el cliente CRM - Soporte.

.. inheritref:: helpdesk/helpdesk:section:asignar_tiques_a_empleados

Asignar tiques a empleados
==========================

Un usuario del grupo de soporte de cada sección, podrá asignar cada
tique que entre en el sistema a un empleado. Este usuario será el encargado
de asignar los tiques que vayan llegando con el empleado a realizar.

.. inheritref:: helpdesk/helpdesk:section:cambiar_de_seccion

Cambiar de sección
==================

En los tiques se dispone de una acción para ejecutar un asistente para cambiar el tique 
de sección (según las secciones que disponga).
Para cambiar de sección deberemos seleccionar a que sección queremos mover el tiquet. También
podemos seleccionar el empleado a que se asignará el tique.

.. inheritref:: helpdesk/helpdesk:section:recepcion_de_correos

Recepción de correos
====================

Los correos electrónicos pueden generar automáticamente nuevos tiques de soporte.
La recepción del correo se configura mediante el módulo Getmail o similar. El tiempo
de recepción viene especificado según la acción planificada.

.. inheritref:: helpdesk/helpdesk:section:envio_de_correo

Envío de correo
===============

En el tique del soporte dispondremos de las comunicaciones que se han realizado con el cliente
(conversaciones). En una comunicación podemos que se envíe el correo electrónico o añadir
una nota.

.. inheritref:: helpdesk/helpdesk:section:adjuntos

Adjuntos
========

En el tique de soporte podemos adjuntar o relacionar con adjuntos. Para más información del uso de adjuntos
consulte el apartado de conceptos básicos.

Para la recepción de correo y adjuntos en el soporte dependerá de la configuración de la cuenta de Getmail si
se permiten la recepción de adjuntos. En el caso afirmativo, en el tique dispondrá de todos los adjuntos en la
pestaña "Adjuntos" en el caso que el correo electrónico disponga de adjuntos.

Recuerde de eliminar los adjuntos si no son necesarios que haya recibido para ahorrar espacio del disco duro (por ejemplo,
imágenes como firmas, logos, etc que haya adjuntado el usuario).

Para el envío de adjuntos, antes de enviar el correo, en la pestaña "Adjuntos" también dispone de un campo que podrá
seleccionar los adjuntos relacionados con el tique para el envío. Los ficheros seleccionados serán añadidos en el correo
en el momento de enviar el correo. El tiempo de envío dependerá del tamaño de los ficheros. Una vez enviado el correo,
los adjuntos en este campo ya no estarán disponibles. Si necesita adjuntar en otra ocasión, siempre los podrá adjuntar de
nuevo.
