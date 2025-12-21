
def get_interaction_context(db: Session, interaction_id: int, window=3):
    """
    Finds surrounding messages for a given interaction ID to provide context (e.g. finding amounts).
    Returns a combined string of previous/next messages.
    """
    target = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not target: return ""
    
    # Simple ID-based window. Assuming sequential IDs roughly correspond to time.
    # Logic: Get interactions with ID in [id-window, id+window] ordered by ID
    min_id = max(1, interaction_id - window)
    max_id = interaction_id + window
    
    neighbors = db.query(Interaction).filter(
        Interaction.id >= min_id, 
        Interaction.id <= max_id
    ).order_by(Interaction.id).all()
    
    context_text = " ".join([n.content for n in neighbors])
    return context_text
