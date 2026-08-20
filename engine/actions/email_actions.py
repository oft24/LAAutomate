"""Enviar/leer correo. Outlook via COM si esta instalado; si no, SMTP/IMAP."""
from __future__ import annotations

import datetime as dt

OL_FOLDER_INBOX = 6


class EmailActions:
    def __init__(self, logger) -> None:
        self.logger = logger

    def enviar_outlook(self, para: str, asunto: str, cuerpo: str) -> None:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        correo = outlook.CreateItem(0)
        correo.To, correo.Subject, correo.Body = para, asunto, cuerpo
        correo.Send()
        self.logger.info("Correo enviado a %s: %s", para, asunto)

    def buscar_outlook_por_remitente(
        self, remitente: str, desde: dt.datetime, carpeta: int = OL_FOLDER_INBOX
    ) -> list[dict]:
        """Busca en una carpeta de Outlook (Bandeja de entrada por defecto)
        los correos de `remitente` recibidos a partir de `desde`.

        Recorre ordenado por fecha descendente y corta en el primer correo
        mas viejo que `desde` -- evita el filtro Restrict() de Outlook, cuyo
        formato de fecha depende de la configuracion regional de Windows.
        """
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        bandeja = outlook.GetDefaultFolder(carpeta)
        items = bandeja.Items
        items.Sort("[ReceivedTime]", True)

        remitente = remitente.lower()
        resultados: list[dict] = []
        for item in items:
            try:
                recibido = item.ReceivedTime
                recibido = dt.datetime(
                    recibido.year, recibido.month, recibido.day, recibido.hour, recibido.minute, recibido.second
                )
            except Exception:
                continue

            if recibido < desde:
                break  # ya pasamos el corte de fecha; lo que sigue es mas viejo

            direccion = self._direccion_smtp(item)
            if direccion and direccion.lower() == remitente:
                resultados.append(
                    {
                        "asunto": getattr(item, "Subject", ""),
                        "recibido": recibido,
                        "remitente": direccion,
                    }
                )

        return resultados

    @staticmethod
    def _direccion_smtp(item) -> str | None:
        """El correo de un remitente interno de Exchange llega como un DN
        tipo 'EX', no como direccion SMTP -- hay que resolverlo aparte o el
        filtro por direccion nunca hace match."""
        try:
            if item.SenderEmailType == "EX":
                return item.Sender.GetExchangeUser().PrimarySmtpAddress
        except Exception:
            pass
        try:
            return item.SenderEmailAddress
        except Exception:
            return None

    def enviar_smtp(self, host: str, puerto: int, usuario: str, password: str, para: str, asunto: str, cuerpo: str) -> None:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = usuario, para, asunto
        msg.set_content(cuerpo)
        with smtplib.SMTP_SSL(host, puerto) as smtp:
            smtp.login(usuario, password)
            smtp.send_message(msg)
