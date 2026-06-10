#!/usr/bin/env python
"""
Script para crear datos de prueba para testear el sistema de billing.
Crea 2 BUs con diferentes planes y usuarios para probar cuotas y avisos.

Uso: python scripts/setup_test_billing.py
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import AsyncSessionLocal
from app.db.models import (
    BusinessUnit, User, UserBUAccess, Plan, BUPlan, PromptConfig
)
from app.services.security import hash_password


async def setup_test_data():
    """Crea BUs, usuarios y planes para testing."""
    async with AsyncSessionLocal() as db:
        print("[SETUP] Configurando datos de prueba...")

        # ─────────────────────────────────────────────────────────────
        # 1. BU con Plan STARTER (para probar overages)
        # ─────────────────────────────────────────────────────────────
        print("\n[BU] Creando BU #1: 'Test Abogados' (Plan STARTER)")

        bu1 = BusinessUnit(
            name="Test Abogados",
            code="TEST_ABAN",
            is_active=True,
        )
        db.add(bu1)
        await db.flush()

        # Usuario para la BU1
        user1 = User(
            email="admin@test-abogados.es",
            full_name="Admin Abogados",
            password_hash=hash_password("password123"),
            is_global_admin=False,
            is_active=True,
        )
        db.add(user1)
        await db.flush()

        # Acceso a BU1
        access1 = UserBUAccess(
            user_id=user1.id,
            bu_id=bu1.id,
            role="bu_admin",
        )
        db.add(access1)

        # Obtener plan STARTER
        stmt_starter = select(Plan).where(Plan.code == "starter")
        result = await db.execute(stmt_starter)
        plan_starter = result.scalar_one_or_none()

        if plan_starter:
            bu_plan1 = BUPlan(
                bu_id=bu1.id,
                plan_id=plan_starter.id,
            )
            db.add(bu_plan1)
            print(f"  [OK] Plan: STARTER (100 docs/mes, 200 extracciones/mes)")
            print(f"  [OK] Overage: SI (0,20EUR/doc, 0,10EUR/extraccion)")
        else:
            print("  [ERROR] Plan STARTER no encontrado")

        # ─────────────────────────────────────────────────────────────
        # 2. BU con Plan GRATUITO (para probar rechazo de overages)
        # ─────────────────────────────────────────────────────────────
        print("\n[BU] Creando BU #2: 'Test Startup' (Plan GRATUITO)")

        bu2 = BusinessUnit(
            name="Test Startup",
            code="TEST_STARTUP",
            is_active=True,
        )
        db.add(bu2)
        await db.flush()

        # Usuario para la BU2
        user2 = User(
            email="dev@test-startup.es",
            full_name="Dev Startup",
            password_hash=hash_password("password123"),
            is_global_admin=False,
            is_active=True,
        )
        db.add(user2)
        await db.flush()

        # Acceso a BU2
        access2 = UserBUAccess(
            user_id=user2.id,
            bu_id=bu2.id,
            role="bu_user",
        )
        db.add(access2)

        # Obtener plan FREE
        stmt_free = select(Plan).where(Plan.code == "free")
        result = await db.execute(stmt_free)
        plan_free = result.scalar_one_or_none()

        if plan_free:
            bu_plan2 = BUPlan(
                bu_id=bu2.id,
                plan_id=plan_free.id,
            )
            db.add(bu_plan2)
            print(f"  [OK] Plan: GRATUITO (10 docs/mes, 20 extracciones/mes)")
            print(f"  [OK] Overage: NO (se rechaza)")
        else:
            print("  [ERROR] Plan FREE no encontrado")

        # ─────────────────────────────────────────────────────────────
        # 3. Crear un prompt config para poder hacer extracciones
        # ─────────────────────────────────────────────────────────────
        print("\n[CONFIG] Creando configuracion de prompt para extracciones...")

        prompt_config = PromptConfig(
            bu_id=bu1.id,
            name="Extracción de facturas",
            model="gpt-4o-mini",
            base_prompt="Extrae los datos de la factura: NIF, empresa, importe",
            variables=[
                {
                    "name": "NIF",
                    "description": "NIF de la empresa",
                    "required": True,
                    "type": "string",
                },
                {
                    "name": "Empresa",
                    "description": "Nombre de la empresa",
                    "required": True,
                    "type": "string",
                },
                {
                    "name": "Importe",
                    "description": "Importe total",
                    "required": True,
                    "type": "number",
                }
            ],
            is_active=True,
        )
        db.add(prompt_config)
        await db.flush()

        # ─────────────────────────────────────────────────────────────
        # Guardar
        # ─────────────────────────────────────────────────────────────
        await db.commit()

        print("\n[OK] Datos de prueba creados exitosamente!\n")
        print("=" * 70)
        print("CREDENCIALES PARA TESTING")
        print("=" * 70)
        print("\n[CREDS] BU #1: Test Abogados (Plan STARTER)")
        print(f"   Email: {user1.email}")
        print(f"   Contrasena: password123")
        print(f"   Limites: 100 docs/mes, 200 extracciones/mes")
        print(f"   Overage: SI (0,20EUR/doc, 0,10EUR/extraccion)")
        print(f"   BU Code: {bu1.code}")
        print(f"   User ID: {user1.id}")

        print("\n[CREDS] BU #2: Test Startup (Plan GRATUITO)")
        print(f"   Email: {user2.email}")
        print(f"   Contrasena: password123")
        print(f"   Limites: 10 docs/mes, 20 extracciones/mes")
        print(f"   Overage: NO (rechaza)")
        print(f"   BU Code: {bu2.code}")
        print(f"   User ID: {user2.id}")

        print("\n" + "=" * 70)
        print("PLAN DE TESTING SUGERIDO")
        print("=" * 70)
        print("""
1. LOGIN con Test Abogados
   - POST /auth/login
   - Email: admin@test-abogados.es / password123

2. SUBIR DOCUMENTOS (hasta 100)
   - POST /documents con X-BU-ID header
   - Verificar avisos en respuesta:
     * 80 docs: aviso "approaching_limit" 80%
     * 90 docs: aviso "approaching_limit" 90%
     * 95 docs: aviso "approaching_limit" 95%
     * 101 docs: aviso "overage_charge" (0,20€)

3. EXTRACCIONES (hasta 200)
   - POST /extract
   - Verificar mismo patrón de avisos

4. TEST CON PLAN GRATUITO (Test Startup)
   - POST /documents - debe rechazar en doc #11
   - Error 429: "Cuota de documentos alcanzada"

5. VERIFICAR DATOS EN BD
   - SELECT * FROM usage_events WHERE bu_id = ?
   - Debe haber: DOC_UPLOADED, EXTRACTION_RUN, overage.doc.upload, overage.extraction.run
""")

        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(setup_test_data())
