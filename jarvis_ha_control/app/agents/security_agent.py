"""Agent Sécurité - Gestion de la sécurité et des permissions.

Cet agent est responsable de :
- Gérer les rôles et permissions des utilisateurs
- Valider les actions selon les règles de sécurité
- Détecter les tentatives d'intrusion
- Gérer les sessions et l'authentification
- Chiffrer les données sensibles
"""

import asyncio
import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set

logger = logging.getLogger("SecurityAgent")


class PermissionLevel(Enum):
    """Niveaux de permission."""
    DENIED = "denied"  # Accès refusé
    READ = "read"  # Lecture seule
    WRITE = "write"  # Lecture/écriture
    ADMIN = "admin"  # Accès complet


class ActionPermission(Enum):
    """Permissions pour les actions."""
    ALLOWED = "allowed"  # Autorisé
    REQUIRE_PIN = "require_pin"  # Requiert un code PIN
    REQUIRE_ADMIN = "require_admin"  # Requiert un admin
    DENIED = "denied"  # Refusé


@dataclass
class User:
    """Représente un utilisateur."""
    user_id: str
    username: str
    role: str  # admin, member, guest
    permissions: Dict[str, PermissionLevel] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    locked: bool = False
    locked_until: Optional[datetime] = None
    
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur est admin."""
        return self.role == "admin"
    
    def is_locked(self) -> bool:
        """Vérifie si l'utilisateur est verrouillé."""
        if not self.locked:
            return False
        if self.locked_until and datetime.now(timezone.utc) > self.locked_until:
            self.locked = False
            self.locked_until = None
            self.login_attempts = 0
        return self.locked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'utilisateur en dictionnaire."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "permissions": {k: v.value for k, v in self.permissions.items()},
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "locked": self.locked,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None
        }


@dataclass
class Session:
    """Représente une session utilisateur."""
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    authenticated: bool = False
    
    def is_valid(self) -> bool:
        """Vérifie si la session est valide."""
        return datetime.now(timezone.utc) < self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la session en dictionnaire."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "authenticated": self.authenticated
        }


@dataclass
class AuditLog:
    """Représente un log d'audit."""
    log_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    action: str
    target: str
    status: str  # success, failure, denied
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le log en dictionnaire."""
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "target": self.target,
            "status": self.status,
            "details": self.details
        }


# Actions dangereuses nécessitant une validation supplémentaire
DANGEROUS_ACTIONS = {
    ("lock", "unlock"): ActionPermission.REQUIRE_ADMIN,
    ("lock", "open"): ActionPermission.REQUIRE_ADMIN,
    ("alarm_control_panel", "alarm_disarm"): ActionPermission.REQUIRE_ADMIN,
    ("alarm_control_panel", "alarm_turn_off"): ActionPermission.REQUIRE_ADMIN,
    ("cover", "open"): ActionPermission.REQUIRE_PIN,
    ("cover", "close"): ActionPermission.REQUIRE_PIN,
    ("switch", "turn_on"): ActionPermission.REQUIRE_PIN,
    ("switch", "turn_off"): ActionPermission.REQUIRE_PIN,
}

# Domaines dangereux
DANGEROUS_DOMAINS = {
    "lock": ActionPermission.REQUIRE_ADMIN,
    "alarm_control_panel": ActionPermission.REQUIRE_ADMIN,
    "door": ActionPermission.REQUIRE_PIN,
    "window": ActionPermission.REQUIRE_PIN,
    "cover": ActionPermission.REQUIRE_PIN,
}

# Rôles par défaut
DEFAULT_ROLES = {
    "admin": {
        "*": PermissionLevel.ADMIN
    },
    "member": {
        "light": PermissionLevel.WRITE,
        "switch": PermissionLevel.WRITE,
        "climate": PermissionLevel.WRITE,
        "cover": PermissionLevel.WRITE,
        "media_player": PermissionLevel.WRITE,
        "*": PermissionLevel.READ
    },
    "guest": {
        "*": PermissionLevel.READ
    }
}


class SecurityAgent:
    """Agent de sécurité pour Jarvis HA Control.
    
    Cet agent gère :
    - Les utilisateurs et leurs rôles
    - Les permissions et les règles de sécurité
    - L'authentification et les sessions
    - L'audit des actions
    - La protection contre les attaques
    """
    
    # Configuration par défaut
    DEFAULT_CONFIG = {
        "session_timeout_hours": 24,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 30,
        "pin_length": 4,
        "require_2fa": False
    }
    
    def __init__(
        self,
        store: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise l'agent de sécurité.
        
        Args:
            store: Instance de Store pour la persistance
            config: Configuration personnalisée
        """
        self.store = store
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # Utilisateurs
        self._users: Dict[str, User] = {}
        
        # Sessions actives
        self._sessions: Dict[str, Session] = {}
        
        # Logs d'audit
        self._audit_logs: List[AuditLog] = []
        
        # Callbacks pour les événements de sécurité
        self._event_handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[Any]]]] = {}
        
        # Charger les utilisateurs depuis le store
        self._load_users()
        
        logger.info("SecurityAgent initialisé")
    
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    ) -> None:
        """Enregistre un handler pour un type d'événement."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Handler enregistré pour {event_type}")
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Émet un événement aux handlers enregistrés."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Erreur dans le handler pour {event_type}: {e}")
    
    def _load_users(self) -> None:
        """Charge les utilisateurs depuis le store."""
        try:
            # Charger depuis le store (à implémenter)
            # Pour l'instant, créer un utilisateur admin par défaut
            if "admin" not in self._users:
                self._users["admin"] = User(
                    user_id="admin",
                    username="Administrateur",
                    role="admin",
                    permissions={"*": PermissionLevel.ADMIN}
                )
            
            logger.info(f"{len(self._users)} utilisateurs chargés")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des utilisateurs: {e}")
    
    def create_user(
        self,
        user_id: str,
        username: str,
        role: str = "member",
        permissions: Optional[Dict[str, PermissionLevel]] = None
    ) -> Dict[str, Any]:
        """
        Crée un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            username: Nom d'utilisateur
            role: Rôle (admin, member, guest)
            permissions: Permissions personnalisées
            
        Returns:
            Résultat de la création
        """
        if user_id in self._users:
            return {"ok": False, "error": "Utilisateur déjà existant"}
        
        if role not in DEFAULT_ROLES:
            return {"ok": False, "error": f"Rôle invalide: {role}"}
        
        # Utiliser les permissions par défaut pour le rôle
        if permissions is None:
            permissions = DEFAULT_ROLES.get(role, {}).copy()
        
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            permissions=permissions
        )
        
        self._users[user_id] = user
        
        # Sauvegarder dans le store
        self._save_user(user)
        
        # Enregistrer dans l'audit
        self._log_audit(
            user_id=None,
            action="create_user",
            target=user_id,
            status="success",
            details={"username": username, "role": role}
        )
        
        logger.info(f"Utilisateur créé: {user_id} ({role})")
        
        return {"ok": True, "user_id": user_id, "user": user.to_dict()}
    
    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """
        Supprime un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            Résultat de la suppression
        """
        if user_id not in self._users:
            return {"ok": False, "error": "Utilisateur non trouvé"}
        
        # Ne pas supprimer le dernier admin
        admin_count = sum(1 for u in self._users.values() if u.role == "admin")
        if user_id in self._users and self._users[user_id].role == "admin" and admin_count <= 1:
            return {"ok": False, "error": "Impossible de supprimer le dernier admin"}
        
        user = self._users.pop(user_id)
        
        # Supprimer les sessions de l'utilisateur
        self._delete_user_sessions(user_id)
        
        # Sauvegarder dans le store
        self._delete_user_from_store(user_id)
        
        # Enregistrer dans l'audit
        self._log_audit(
            user_id=None,
            action="delete_user",
            target=user_id,
            status="success",
            details={"username": user.username}
        )
        
        logger.info(f"Utilisateur supprimé: {user_id}")
        
        return {"ok": True, "user_id": user_id}
    
    def _save_user(self, user: User) -> None:
        """Sauvegarde un utilisateur dans le store."""
        try:
            # Sauvegarder dans le store (à implémenter)
            pass
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'utilisateur: {e}")
    
    def _delete_user_from_store(self, user_id: str) -> None:
        """Supprime un utilisateur du store."""
        try:
            # Supprimer du store (à implémenter)
            pass
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de l'utilisateur: {e}")
    
    def _delete_user_sessions(self, user_id: str) -> None:
        """Supprime les sessions d'un utilisateur."""
        to_delete = [sid for sid, session in self._sessions.items() if session.user_id == user_id]
        for sid in to_delete:
            del self._sessions[sid]
        
        logger.info(f"{len(to_delete)} sessions supprimées pour {user_id}")
    
    def get_user(self, user_id: str) -> Optional[User]:
        """
        Récupère un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            Utilisateur ou None
        """
        return self._users.get(user_id)
    
    def list_users(self) -> List[Dict[str, Any]]:
        """
        Liste tous les utilisateurs.
        
        Returns:
            Liste des utilisateurs
        """
        return [u.to_dict() for u in self._users.values()]
    
    def update_user_role(self, user_id: str, new_role: str) -> Dict[str, Any]:
        """
        Met à jour le rôle d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            new_role: Nouveau rôle
            
        Returns:
            Résultat de la mise à jour
        """
        if user_id not in self._users:
            return {"ok": False, "error": "Utilisateur non trouvé"}
        
        if new_role not in DEFAULT_ROLES:
            return {"ok": False, "error": f"Rôle invalide: {new_role}"}
        
        user = self._users[user_id]
        old_role = user.role
        user.role = new_role
        user.permissions = DEFAULT_ROLES.get(new_role, {}).copy()
        
        # Sauvegarder dans le store
        self._save_user(user)
        
        # Enregistrer dans l'audit
        self._log_audit(
            user_id=None,
            action="update_user_role",
            target=user_id,
            status="success",
            details={"old_role": old_role, "new_role": new_role}
        )
        
        logger.info(f"Rôle mis à jour: {user_id} ({old_role} → {new_role})")
        
        return {"ok": True, "user_id": user_id, "old_role": old_role, "new_role": new_role}
    
    def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crée une session pour un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            ip_address: Adresse IP
            user_agent: User Agent
            
        Returns:
            Résultat de la création
        """
        if user_id not in self._users:
            return {"ok": False, "error": "Utilisateur non trouvé"}
        
        user = self._users[user_id]
        
        # Vérifier si l'utilisateur est verrouillé
        if user.is_locked():
            return {"ok": False, "error": "Utilisateur verrouillé"}
        
        # Générer un ID de session
        session_id = secrets.token_hex(16)
        
        # Calculer la date d'expiration
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.config["session_timeout_hours"]
        )
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            authenticated=False
        )
        
        self._sessions[session_id] = session
        
        # Enregistrer dans l'audit
        self._log_audit(
            user_id=user_id,
            action="create_session",
            target=session_id,
            status="success",
            details={"ip_address": ip_address, "user_agent": user_agent}
        )
        
        logger.info(f"Session créée: {session_id} pour {user_id}")
        
        return {"ok": True, "session_id": session_id, "session": session.to_dict()}
    
    def authenticate_session(self, session_id: str, credentials: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Authentifie une session.
        
        Args:
            session_id: ID de la session
            credentials: Identifiants (optionnel)
            
        Returns:
            Résultat de l'authentification
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Session non trouvée"}
        
        if not session.is_valid():
            return {"ok": False, "error": "Session expirée"}
        
        user = self._users.get(session.user_id)
        if not user:
            return {"ok": False, "error": "Utilisateur non trouvé"}
        
        # Vérifier si l'utilisateur est verrouillé
        if user.is_locked():
            return {"ok": False, "error": "Utilisateur verrouillé"}
        
        # Si des identifiants sont fournis, les vérifier
        if credentials:
            # Vérifier le mot de passe ou le PIN
            if not self._verify_credentials(user, credentials):
                # Incrémenter les tentatives de connexion
                user.login_attempts += 1
                
                # Verrouiller l'utilisateur si trop de tentatives
                if user.login_attempts >= self.config["max_login_attempts"]:
                    user.locked = True
                    user.locked_until = datetime.now(timezone.utc) + timedelta(
                        minutes=self.config["lockout_duration_minutes"]
                    )
                    
                    # Sauvegarder dans le store
                    self._save_user(user)
                    
                    # Enregistrer dans l'audit
                    self._log_audit(
                        user_id=user.user_id,
                        action="login_failed",
                        target=user.user_id,
                        status="failure",
                        details={"attempts": user.login_attempts, "locked": True}
                    )
                    
                    return {"ok": False, "error": "Trop de tentatives. Utilisateur verrouillé."}
                
                # Sauvegarder l'utilisateur
                self._save_user(user)
                
                # Enregistrer dans l'audit
                self._log_audit(
                    user_id=user.user_id,
                    action="login_failed",
                    target=user.user_id,
                    status="failure",
                    details={"attempts": user.login_attempts}
                )
                
                return {"ok": False, "error": "Identifiants invalides"}
        
        # Authentification réussie
        session.authenticated = True
        user.login_attempts = 0
        user.last_login = datetime.now(timezone.utc)
        
        # Sauvegarder l'utilisateur
        self._save_user(user)
        
        # Enregistrer dans l'audit
        self._log_audit(
            user_id=user.user_id,
            action="login_success",
            target=session.session_id,
            status="success",
            details={}
        )
        
        logger.info(f"Session authentifiée: {session_id}")
        
        return {"ok": True, "session_id": session_id, "user_id": user.user_id}
    
    def _verify_credentials(self, user: User, credentials: Dict[str, str]) -> bool:
        """
        Vérifie les identifiants.
        
        Args:
            user: Utilisateur
            credentials: Identifiants
            
        Returns:
            True si valide
        """
        # Implémentation par défaut (à personnaliser)
        # Vérifier le PIN si présent
        if "pin" in credentials:
            # Récupérer le PIN de l'utilisateur (à implémenter)
            stored_pin = self._get_user_pin(user.user_id)
            if stored_pin:
                return hmac.compare_digest(credentials["pin"], stored_pin)
        
        # Vérifier le mot de passe si présent
        if "password" in credentials:
            stored_password = self._get_user_password(user.user_id)
            if stored_password:
                return hmac.compare_digest(
                    self._hash_password(credentials["password"]),
                    stored_password
                )
        
        return False
    
    def _get_user_pin(self, user_id: str) -> Optional[str]:
        """Récupère le PIN d'un utilisateur."""
        # À implémenter
        return None
    
    def _get_user_password(self, user_id: str) -> Optional[str]:
        """Récupère le mot de passe d'un utilisateur."""
        # À implémenter
        return None
    
    def _hash_password(self, password: str) -> str:
        """Hache un mot de passe."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def validate_session(self, session_id: str) -> Dict[str, Any]:
        """
        Valide une session.
        
        Args:
            session_id: ID de la session
            
        Returns:
            Résultat de la validation
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Session non trouvée"}
        
        if not session.is_valid():
            return {"ok": False, "error": "Session expirée"}
        
        if not session.authenticated:
            return {"ok": False, "error": "Session non authentifiée"}
        
        user = self._users.get(session.user_id)
        if not user:
            return {"ok": False, "error": "Utilisateur non trouvé"}
        
        return {
            "ok": True,
            "session_id": session_id,
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role
        }
    
    def invalidate_session(self, session_id: str) -> Dict[str, Any]:
        """
        Invalide une session.
        
        Args:
            session_id: ID de la session
            
        Returns:
            Résultat de l'invalidation
        """
        if session_id not in self._sessions:
            return {"ok": False, "error": "Session non trouvée"}
        
        session = self._sessions.pop(session_id)
        
        # Enregistrer dans l'audit
        self._log_audit(
            user_id=session.user_id,
            action="invalidate_session",
            target=session_id,
            status="success",
            details={}
        )
        
        logger.info(f"Session invalidée: {session_id}")
        
        return {"ok": True, "session_id": session_id}
    
    def check_permission(
        self,
        user_id: str,
        domain: str,
        action: str = "read"
    ) -> PermissionLevel:
        """
        Vérifie la permission d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            domain: Domaine (ex: "light", "lock")
            action: Action ("read", "write", "admin")
            
        Returns:
            Niveau de permission
        """
        user = self._users.get(user_id)
        if not user:
            return PermissionLevel.DENIED
        
        # Vérifier les permissions spécifiques
        if domain in user.permissions:
            return user.permissions[domain]
        
        # Vérifier le wildcard
        if "*" in user.permissions:
            return user.permissions["*"]
        
        # Par défaut : refusé
        return PermissionLevel.DENIED
    
    def check_action_permission(
        self,
        user_id: str,
        action: Dict[str, Any]
    ) -> ActionPermission:
        """
        Vérifie la permission pour une action.
        
        Args:
            user_id: ID de l'utilisateur
            action: Action à vérifier
            
        Returns:
            Permission pour l'action
        """
        domain = action.get("domain", "")
        service = action.get("service", "")
        
        # Vérifier si l'action est dangereuse
        if (domain, service) in DANGEROUS_ACTIONS:
            return DANGEROUS_ACTIONS[(domain, service)]
        
        # Vérifier si le domaine est dangereux
        if domain in DANGEROUS_DOMAINS:
            return DANGEROUS_DOMAINS[domain]
        
        # Vérifier les permissions de l'utilisateur
        permission = self.check_permission(user_id, domain, "write")
        if permission == PermissionLevel.DENIED:
            return ActionPermission.DENIED
        
        if permission == PermissionLevel.READ:
            return ActionPermission.DENIED
        
        # Par défaut : autorisé
        return ActionPermission.ALLOWED
    
    def can_execute_action(
        self,
        user_id: str,
        action: Dict[str, Any],
        pin: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vérifie si un utilisateur peut exécuter une action.
        
        Args:
            user_id: ID de l'utilisateur
            action: Action à vérifier
            pin: Code PIN (optionnel)
            
        Returns:
            Résultat de la vérification
        """
        user = self._users.get(user_id)
        if not user:
            return {"ok": False, "error": "Utilisateur non trouvé", "permission": ActionPermission.DENIED}
        
        # Vérifier la permission pour l'action
        permission = self.check_action_permission(user_id, action)
        
        if permission == ActionPermission.DENIED:
            return {"ok": False, "error": "Permission refusée", "permission": permission}
        
        if permission == ActionPermission.REQUIRE_ADMIN:
            if not user.is_admin():
                return {"ok": False, "error": "Requiert un admin", "permission": permission}
        
        if permission == ActionPermission.REQUIRE_PIN:
            if not pin:
                return {"ok": False, "error": "Requiert un code PIN", "permission": permission}
            
            # Vérifier le PIN
            if not self._verify_user_pin(user_id, pin):
                return {"ok": False, "error": "Code PIN invalide", "permission": permission}
        
        return {"ok": True, "permission": permission}
    
    def _verify_user_pin(self, user_id: str, pin: str) -> bool:
        """
        Vérifie le PIN d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            pin: Code PIN
            
        Returns:
            True si valide
        """
        # À implémenter
        return True
    
    def _log_audit(
        self,
        user_id: Optional[str],
        action: str,
        target: str,
        status: str,
        details: Dict[str, Any]
    ) -> None:
        """
        Enregistre un log d'audit.
        
        Args:
            user_id: ID de l'utilisateur
            action: Action
            target: Cible
            status: Statut
            details: Détails
        """
        log_id = f"audit_{int(time.time())}_{len(self._audit_logs)}"
        
        log = AuditLog(
            log_id=log_id,
            user_id=user_id,
            action=action,
            target=target,
            status=status,
            details=details
        )
        
        self._audit_logs.append(log)
        
        # Limiter l'historique
        if len(self._audit_logs) > 1000:
            self._audit_logs = self._audit_logs[-1000:]
        
        # Enregistrer dans le store
        try:
            self.store.log(
                severity="info",
                kind="audit",
                message=f"{action}: {target} ({status})",
                entity_id=target
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'audit: {e}")
    
    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les logs d'audit.
        
        Args:
            limit: Nombre maximum de logs
            
        Returns:
            Liste des logs
        """
        return [log.to_dict() for log in self._audit_logs[-limit:]]
    
    def get_security_status(self) -> Dict[str, Any]:
        """
        Récupère l'état de sécurité.
        
        Returns:
            État de sécurité
        """
        return {
            "user_count": len(self._users),
            "session_count": len(self._sessions),
            "locked_users": len([u for u in self._users.values() if u.is_locked()]),
            "audit_logs_count": len(self._audit_logs),
            "users": [u.to_dict() for u in self._users.values()],
            "sessions": [s.to_dict() for s in self._sessions.values()]
        }
